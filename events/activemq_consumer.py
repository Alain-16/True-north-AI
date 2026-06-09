import asyncio
import logging
import threading
import time

import stomp

from core.config import get_settings
from events.handlers import (
      TOPIC_RESOURCE_TYPE,
      EVENT_HANDLERS,
      parse_event,
  )

logger = logging.getLogger(__name__)

DESTINATIONS = list(TOPIC_RESOURCE_TYPE.keys())
RECONNECT_DELAY = 5  # seconds between reconnect attempts


def _log_future_error(fut) -> None:
    try:
        fut.result()
    except Exception:
        logger.exception("event handler failed")     # was "handle_report_event failed"



def _host_port(url: str) -> tuple[str, int]:
      cleaned = url.split("://")[-1]
      host, _, port = cleaned.partition(":")
      return host or "localhost", int(port or 61613)


class ReportEventListener(stomp.ConnectionListener):
      def __init__(self, loop, consumer):
          self._loop = loop
          self._consumer = consumer

      def on_error(self, frame) -> None:
          logger.error("STOMP error frame: %s", frame.body)

      def on_disconnected(self) -> None:
          logger.warning("STOMP disconnected from ActiveMQ")
          self._consumer.handle_disconnect()



      def on_message(self, frame) -> None:
        event = parse_event(frame.headers.get("destination", ""), frame.body)
        if event is None:
            return

        handler = EVENT_HANDLERS.get(event["resource_type"])     # noqa: F821
        if handler is None:
            return

        fut = asyncio.run_coroutine_threadsafe(handler(event), self._loop)   # noqa: F821
        fut.add_done_callback(_log_future_error)



class ActiveMQConsumer:
      def __init__(self):
          self._conn = None
          self._loop = None
          self._stopping = False
          self._reconnecting = False
          self._lock = threading.Lock()

      def start(self, loop) -> None:
          self._loop = loop
          self._stopping = False
          self._connect()

      def _connect(self) -> None:
          settings = get_settings()
          host, port = _host_port(settings.activemq_url)

          conn = stomp.Connection([(host, port)], heartbeats=(10000, 0))
          conn.set_listener("report-events", ReportEventListener(self._loop, self))
          conn.connect(settings.activemq_username, settings.activemq_password, wait=True)
          for sub_id, dest in enumerate(DESTINATIONS, start=1):
              conn.subscribe(destination=dest, id=str(sub_id), ack="auto",
                             headers={"transformation": "jms-map-json"})
              logger.info("Subscribed to %s", dest)
          self._conn = conn

      def handle_disconnect(self) -> None:

          if self._stopping:
              return
          with self._lock:
              if self._reconnecting:
                  return            
              self._reconnecting = True
          threading.Thread(target=self._reconnect_loop, daemon=True).start()

      def _reconnect_loop(self) -> None:
          try:
              while not self._stopping:
                  time.sleep(RECONNECT_DELAY)
                  if self._stopping:
                      return
                  try:
                      logger.info("Attempting STOMP reconnect…")
                      self._connect()
                      logger.info("STOMP reconnected")
                      return
                  except Exception:
                      logger.exception("STOMP reconnect failed; retrying in %ss", RECONNECT_DELAY)
          finally:
              with self._lock:
                  self._reconnecting = False

      def stop(self) -> None:
          self._stopping = True
          if self._conn is not None:
              try:
                  self._conn.disconnect()
              except Exception:
                  logger.exception("Error disconnecting STOMP")
              self._conn = None


consumer = ActiveMQConsumer()

