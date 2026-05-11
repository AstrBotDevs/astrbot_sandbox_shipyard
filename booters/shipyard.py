from __future__ import annotations

import shlex
from dataclasses import asdict, is_dataclass
from typing import Any

import aiohttp
from shipyard import FileSystemComponent as ShipyardFileSystemComponent
from shipyard import ShipyardClient, Spec

from astrbot.api import logger
from astrbot.core.computer.booters.base import ComputerBooter
from astrbot.core.computer.olayer import (
    FileSystemComponent,
    PythonComponent,
    ShellComponent,
)

from .shell_background import build_detached_shell_command
from .shipyard_search_file_util import search_files_via_shell

_SHELL_RESULT_ATTRS: tuple[str, ...] = (
    "stdout",
    "stderr",
    "output",
    "error",
    "returncode",
    "return_code",
    "exit_code",
    "success",
    "execution_id",
    "execution_time_ms",
    "command",
)
_SHIP_DELETE_TIMEOUT_S = 30


def _build_shell_payload_from_attrs(value: Any) -> dict[str, Any]:
    return {
        key: getattr(value, key) for key in _SHELL_RESULT_ATTRS if hasattr(value, key)
    }


def _to_payload_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return dict(value)
    if is_dataclass(value) and not isinstance(value, type):
        return asdict(value)
    for method_name in ("model_dump", "dict"):
        method = getattr(value, method_name, None)
        if not callable(method):
            continue
        try:
            dumped = method()
        except Exception:
            dumped = None
        if isinstance(dumped, dict):
            return dict(dumped)
    return _build_shell_payload_from_attrs(value)


def _flatten_data_field(payload: dict[str, Any]) -> dict[str, Any]:
    data = payload.get("data")
    if not isinstance(data, dict):
        return payload
    merged = dict(payload)
    merged.update(data)
    return merged


def _first(payload: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in payload:
            return payload[key]
    return None


def _normalize_shell_aliases(payload: dict[str, Any]) -> dict[str, Any]:
    stdout = _first(payload, "output", "stdout")
    stderr = _first(payload, "error", "stderr")
    exit_code = _first(payload, "exit_code", "return_code", "returncode")
    if stdout is not None:
        payload["stdout"] = stdout
    if stderr is not None:
        payload["stderr"] = stderr
    if exit_code is not None:
        payload["exit_code"] = exit_code
    return payload


async def _delete_ship_via_api(
    endpoint_url: str, access_token: str, ship_id: str
) -> None:
    headers = {"Authorization": f"Bearer {access_token}"}
    timeout = aiohttp.ClientTimeout(total=_SHIP_DELETE_TIMEOUT_S)
    async with aiohttp.ClientSession(headers=headers, timeout=timeout) as session:
        async with session.delete(f"{endpoint_url}/ship/{ship_id}") as response:
            if response.status not in {200, 202, 204, 404}:
                error_text = await response.text()
                raise RuntimeError(
                    f"Failed to delete ship: {response.status} {error_text}"
                )


def _normalize_shell_result(value: Any) -> dict[str, Any]:
    payload = _to_payload_dict(value)
    payload = _flatten_data_field(payload)
    return _normalize_shell_aliases(payload)


class ShipyardShellWrapper:
    def __init__(self, _shipyard_shell: ShellComponent):
        self._shell = _shipyard_shell

    async def exec(
        self,
        command: str,
        cwd: str | None = None,
        env: dict[str, str] | None = None,
        timeout: int | None = 300,
        shell: bool = True,
        background: bool = False,
    ) -> dict[str, Any]:
        if not shell:
            return {
                "stdout": "",
                "stderr": "error: only shell mode is supported in shipyard booter.",
                "exit_code": 2,
                "success": False,
            }

        run_command = command
        if env:
            env_prefix = " ".join(
                f"{k}={shlex.quote(str(v))}" for k, v in sorted(env.items())
            )
            run_command = f"{env_prefix} {run_command}"

        if background:
            run_command = build_detached_shell_command(run_command)

        result = await self._shell.exec(
            run_command,
            timeout=timeout or 300,
            cwd=cwd,
        )
        payload = _normalize_shell_result(result)

        stdout = payload.get("stdout") or ""
        stderr = payload.get("stderr") or ""
        exit_code = payload.get("exit_code")
        if background:
            pid: int | None = None
            try:
                pid = int(str(stdout).strip().splitlines()[-1])
            except Exception:
                pid = None
            return {
                "pid": pid,
                "stdout": (
                    f"Command is running in the background. pid={pid}"
                    if pid is not None
                    else "Command was submitted in the background."
                ),
                "stderr": stderr,
                "exit_code": exit_code,
                "success": bool(payload.get("success", not stderr)),
                "execution_id": payload.get("execution_id"),
                "execution_time_ms": payload.get("execution_time_ms"),
                "command": payload.get("command"),
            }

        return {
            "stdout": stdout,
            "stderr": stderr,
            "exit_code": exit_code,
            "success": bool(payload.get("success", not stderr)),
            "execution_id": payload.get("execution_id"),
            "execution_time_ms": payload.get("execution_time_ms"),
            "command": payload.get("command"),
        }


class ShipyardFileSystemWrapper:
    def __init__(
        self, _shipyard_fs: ShipyardFileSystemComponent, _shipyard_shell: ShellComponent
    ):
        self._fs = _shipyard_fs
        self._shell = _shipyard_shell

    async def create_file(
        self, path: str, content: str = "", mode: int = 420
    ) -> dict[str, Any]:
        return await self._fs.create_file(path=path, content=content, mode=mode)

    async def read_file(
        self,
        path: str,
        encoding: str = "utf-8",
        offset: int | None = None,
        limit: int | None = None,
    ) -> dict[str, Any]:
        return await self._fs.read_file(
            path=path, encoding=encoding, offset=offset, limit=limit
        )

    async def write_file(
        self, path: str, content: str, mode: str = "w", encoding: str = "utf-8"
    ) -> dict[str, Any]:
        return await self._fs.write_file(
            path=path, content=content, mode=mode, encoding=encoding
        )

    async def list_dir(
        self, path: str = ".", show_hidden: bool = False
    ) -> dict[str, Any]:
        return await self._fs.list_dir(path=path, show_hidden=show_hidden)

    async def delete_file(self, path: str) -> dict[str, Any]:
        return await self._fs.delete_file(path=path)

    async def search_files(
        self,
        pattern: str,
        path: str | None = None,
        glob: str | None = None,
        after_context: int | None = None,
        before_context: int | None = None,
    ) -> dict[str, Any]:
        return await search_files_via_shell(
            self._shell,
            pattern=pattern,
            path=path,
            glob=glob,
            after_context=after_context,
            before_context=before_context,
        )

    async def edit_file(
        self,
        path: str,
        old_string: str,
        new_string: str,
        replace_all: bool = False,
        encoding: str = "utf-8",
    ) -> dict[str, Any]:
        return await self._fs.edit_file(
            path=path,
            old_string=old_string,
            new_string=new_string,
            replace_all=replace_all,
            encoding=encoding,
        )


class ShipyardBooter(ComputerBooter):
    def __init__(
        self,
        endpoint_url: str,
        access_token: str,
        ttl: int = 3600,
        session_num: int = 10,
    ) -> None:
        self._sandbox_client = ShipyardClient(
            endpoint_url=endpoint_url, access_token=access_token
        )
        self._ttl = ttl
        self._session_num = session_num
        self._failed_boot = False

    async def boot(self, session_id: str) -> None:
        if self._failed_boot:
            raise RuntimeError("Shipyard booter failed to boot and cannot be reused")
        try:
            ship = await self._sandbox_client.create_ship(
                ttl=self._ttl,
                spec=Spec(cpus=1.0, memory="512m"),
                max_session_num=self._session_num,
                session_id=session_id,
            )
        except Exception:
            await self._sandbox_client.close()
            self._failed_boot = True
            raise
        logger.info(f"Got sandbox ship: {ship.id} for session: {session_id}")
        self._ship = ship
        self._shell = ShipyardShellWrapper(self._ship.shell)
        self._fs = ShipyardFileSystemWrapper(self._ship.fs, self._shell)

    async def shutdown(self) -> None:
        logger.info("[Computer] Shipyard booter shutdown.")
        await self._sandbox_client.close()

    async def destroy(self) -> None:
        ship_id = getattr(getattr(self, "_ship", None), "id", None)
        try:
            if ship_id:
                await _delete_ship_via_api(
                    self._sandbox_client.endpoint_url,
                    self._sandbox_client.access_token,
                    ship_id,
                )
        finally:
            await self.shutdown()

    @property
    def fs(self) -> FileSystemComponent:
        return self._fs

    @property
    def python(self) -> PythonComponent:
        return self._ship.python

    @property
    def shell(self) -> ShellComponent:
        return self._shell

    async def upload_file(self, path: str, file_name: str) -> dict:
        """Upload file to sandbox"""
        result = await self._ship.upload_file(path, file_name)
        logger.info("[Computer] File uploaded to Shipyard sandbox: %s", file_name)
        return result

    async def download_file(self, remote_path: str, local_path: str):
        """Download file from sandbox."""
        result = await self._ship.download_file(remote_path, local_path)
        logger.info(
            "[Computer] File downloaded from Shipyard sandbox: %s -> %s",
            remote_path,
            local_path,
        )
        return result

    async def available(self) -> bool:
        """Check if the sandbox is available."""
        try:
            ship_id = self._ship.id
            data = await self._sandbox_client.get_ship(ship_id)
            if not data:
                logger.info(
                    "[Computer] Shipyard sandbox health check: id=%s, healthy=False (no data)",
                    ship_id,
                )
                return False
            health = bool(data.get("status", 0) == 1)
            logger.info(
                "[Computer] Shipyard sandbox health check: id=%s, healthy=%s",
                ship_id,
                health,
            )
            return health
        except Exception as e:
            logger.error(f"Error checking Shipyard sandbox availability: {e}")
            return False
