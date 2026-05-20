from datetime import datetime,timezone
import httpx
from mcp_server.config import get_mcp_settings


class OpenmrsError(Exception):
    def __init__(self,message:str,code:str | None=None, status:int | None=None):
        self.message = message
        self.code = code
        self.status= status
        super().__init__(message)

def to_openmrs_datetime(dt: datetime)-> str:
    if dt.tzinfo is None:
        dt= dt.replace(tzinfo=timezone.utc)
    
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.0Z")

def from_openmrs_datetime(epoch_ms: int)-> datetime:
    return datetime.fromtimestamp(epoch_ms / 1000 , tz=timezone.utc)

class OpenMrsClient:
    def __init__(self):
        settings = get_mcp_settings()
        base= settings.openmrs_base_url
        self._client = httpx.AsyncClient(
            base_url=f"{base}/ws/rest/v1/",
            auth=httpx.BasicAuth(settings.openmrs_username,settings.openmrs_password),
            timeout=30.0,
            verify=False
        )

    async def get(self,path:str,params:dict | None=None) -> dict | list:
        return await self._request("GET",path,params=params)
    async def post(self, path: str, json: dict | None = None) -> dict | list:
          return await self._request("POST", path, json=json)

    async def _request(self, method: str, path: str, **kwargs) -> dict | list:
          try:
              response = await self._client.request(method, path.lstrip("/"), **kwargs)
          except httpx.HTTPError as exc:
              # Fold transport failures (timeout, connection refused) into the
              # one exception type tools and LangGraph nodes catch.
              raise OpenmrsError(f"OpenMRS request failed: {exc}") from exc

          if not response.is_success:
              raise self._parse_error(response)

          # Some endpoints return 200 with an empty body (e.g. providerResponse).
          if not response.content:
              return {}
          return response.json()

    @staticmethod
    def _parse_error(response: httpx.Response) -> OpenmrsError:
          location = response.headers.get("location")
          if location:
                message = f"Openmrs returned HTTP {response.status_code}-> redirect to {location}"
          else:
            message = f"OpenMRS returned HTTP {response.status_code}"
          code = None
          try:
              error = response.json().get("error", {})
              message = error.get("message", message)
              code = error.get("code")
          except (ValueError, AttributeError):
              # A 500 may return HTML, not the {"error": {...}} JSON shape.
              pass
          return OpenmrsError(message, code=code, status=response.status_code)

    @staticmethod
    def _parse_error(response: httpx.Response) -> OpenmrsError:
          message = f"OpenMRS returned HTTP {response.status_code}"
          code = None
          try:
              error = response.json().get("error", {})
              message = error.get("message", message)
              code = error.get("code")
          except (ValueError, AttributeError):
              # A 500 may return HTML, not the {"error": {...}} JSON shape.
              pass
          return OpenmrsError(message, code=code, status=response.status_code)

    async def aclose(self) -> None:
          await self._client.aclose()


client = OpenMrsClient()
