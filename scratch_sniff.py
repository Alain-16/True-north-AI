import time
import stomp
from core.config import get_settings

REAL_TOPICS = [
      "/topic/CREATED:org.openmrs.DrugOrder",
      "/topic/CREATED:org.openmrs.Obs",
  ]


class Sniffer(stomp.ConnectionListener):
      def on_message(self, frame):
          print("=" * 70)
          print("DESTINATION:", frame.headers.get("destination"))
          print("HEADERS:    ", frame.headers)
          print("BODY:       ", repr(frame.body))

def main():
      s = get_settings()
      host, _, port = s.activemq_url.split("://")[-1].partition(":")
      conn = stomp.Connection([(host or "localhost", int(port or 61613))])
      conn.set_listener("sniffer", Sniffer())
      conn.connect(s.activemq_username, s.activemq_password, wait=True)
      for i, dest in enumerate(REAL_TOPICS, start=1):
          # ask ActiveMQ to render JMS MapMessages as JSON
          conn.subscribe(destination=dest, id=str(i), ack="auto",
                         headers={"transformation": "jms-map-json"})
      print("Listening — create a NEW drug order in OpenMRS now. Ctrl+C to stop.")
      try:
          while True:
              time.sleep(1)
      except KeyboardInterrupt:
          conn.disconnect()

if __name__ == "__main__":
      main()
