import mimetypes
import os
import pprint
from enum import Enum
from typing import Union, Dict, List, Optional

import allure
import requests
from http import HTTPStatus

from dotenv import load_dotenv
from requests.adapters import HTTPAdapter, Retry

import json
import uuid

from my_codegen.utils.base_url import BaseUrlSingleton
from my_codegen.utils.logger import allure_report

import threading

_thread_locals = threading.local()

load_dotenv()


def log_step(step_name: str):
    def decorator(func):
        @allure.step(step_name)
        def wrapper(*args, **kwargs):
            _thread_locals.locust_step_name = step_name
            try:
                return func(*args, **kwargs)
            finally:
                _thread_locals.locust_step_name = None

        wrapper.__name__ = step_name
        return wrapper

    return decorator


class UUIDEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, uuid.UUID):
            return str(obj)
        if isinstance(obj, Enum):
            return obj.value
        return super().default(obj)


class RequestHandler:
    def __init__(self, auth_token: Optional[str] = None, session: Optional[requests.Session] = None):
        self.auth_token = auth_token
        self.session = session if session is not None else requests.Session()
        self._configure_retries()

    def _configure_retries(self):
        retries = Retry(
            total=10,
            backoff_factor=2,
            status_forcelist=[502, 504],
            raise_on_status=False,
        )
        adapter = HTTPAdapter(max_retries=retries)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)

    def _add_authorization_header(self, headers: Optional[Dict[str, str]] = None) -> Dict[str, str]:
        headers = headers or {}
        if self.auth_token:
            headers["Authorization"] = f"Bearer {self.auth_token}"
        return headers

    def validate_response(
            self, response: requests.Response, expected_status: Optional[HTTPStatus], method: str,
            payload: Optional[Dict] = None
    ):
        if expected_status and response.status_code != expected_status.value:
            response_text = response.text[:2000]
            payload_str = pprint.pformat(payload) if payload else ""
            error_message = (
                f"Expected status: {expected_status}, actual status: {response.status_code}.\n"
                f"Method: {method}\n"
                f"URL: {response.url}\n"
                f"response: {response_text},"
                f"headers: {response.request.headers}\n"
                f"payload: {payload_str}\n"
            )
            raise AssertionError(error_message)

    def process_response(self, response: requests.Response) -> Union[Dict, List, bytes, str, None]:
        try:
            if "application/pdf" in response.headers.get("Content-Type", "") or "bytes" in response.headers.get(
                    "Accept-Ranges", ""):
                return response.content
            if response.status_code == HTTPStatus.NO_CONTENT:
                return response.text
            return response.json()
        except requests.exceptions.JSONDecodeError:
            return response.text


class ApiClient:
    def __init__(
            self,
            auth_token: Optional[str] = None,
            base_url: Optional[str] = None,
            session: Optional[requests.Session] = None,
    ):
        self.base_url = base_url if base_url else BaseUrlSingleton.get_base_url()
        self.auth_token = auth_token
        self._request_handler = RequestHandler(auth_token, session=session)

    def _send_request(
            self,
            method: str,
            path: str,
            payload: Optional[Union[Dict, List]] = None,
            headers: Optional[Dict] = None,
            params: Optional[Dict] = None,
            files: Optional[Dict] = None,
            expected_status: Optional[HTTPStatus] = None,
            **kwargs,
    ) -> Union[Dict, List, bytes, None]:
        formatted_path = path.format(**kwargs)
        url = f"{self.base_url}{formatted_path}"

        headers = self._request_handler._add_authorization_header(headers)

        # Если имя запроса не передано явно, пробуем взять из thread-local
        name = kwargs.get("name") or getattr(_thread_locals, "locust_step_name", None)

        data = None
        if payload is not None:
            if files is None:
                data = json.dumps(payload, cls=UUIDEncoder)
                if "Content-Type" not in headers:
                    headers["Content-Type"] = "application/json"
            else:
                data = payload

        response = self._request_handler.session.request(
            method=method,
            url=url,
            headers=headers,
            params=params,
            data=data,
            files=files,
            name=name  # передаем полученное имя
        )

        self._request_handler.validate_response(response, expected_status, method, payload or params)
        return self._request_handler.process_response(response)

    def _get(
            self,
            path: str,
            headers: Optional[Dict] = None,
            params: Optional[Dict] = None,
            expected_status: HTTPStatus = HTTPStatus.OK,
            **kwargs,
    ) -> Union[Dict, List]:
        return self._send_request(
            "GET",
            path,
            params=params,
            headers=headers,
            expected_status=expected_status,
            **kwargs,
        )

    def _post(
            self,
            path: str,
            payload: Optional[Union[Dict, List]] = None,
            headers: Optional[Dict] = None,
            files: Optional[Dict] = None,
            expected_status: HTTPStatus = HTTPStatus.CREATED,
            **kwargs,
    ) -> Union[Dict, List]:
        return self._send_request(
            "POST",
            path,
            payload=payload,
            files=files,
            headers=headers,
            expected_status=expected_status,
            **kwargs,
        )

    def _put(
            self,
            path: str = "",
            payload: Optional[Union[Dict, List]] = None,
            params: Optional[Dict] = None,
            headers: Optional[Dict] = None,
            files: Optional[Dict] = None,
            expected_status: HTTPStatus = HTTPStatus.OK,
            **kwargs,
    ) -> Union[Dict, List]:
        return self._send_request(
            "PUT",
            path,
            payload=payload,
            params=params,
            headers=headers,
            files=files,
            expected_status=expected_status,
            **kwargs,
        )

    def _patch(
            self,
            path: str,
            payload: Optional[Union[Dict, List]] = None,
            params: Optional[Dict] = None,
            headers: Optional[Dict] = None,
            expected_status: HTTPStatus = HTTPStatus.OK,
            **kwargs,
    ) -> Union[Dict, List]:
        return self._send_request(
            "PATCH",
            path,
            payload=payload,
            params=params,
            headers=headers,
            expected_status=expected_status,
            **kwargs,
        )

    def _delete(
            self,
            path: str,
            headers: Optional[Dict] = None,
            params: Optional[Dict] = None,
            payload: Optional[Union[Dict, List]] = None,
            expected_status: HTTPStatus = HTTPStatus.NO_CONTENT,
            **kwargs,
    ) -> Union[Dict, List]:
        return self._send_request(
            "DELETE",
            path,
            headers=headers,
            params=params,
            payload=payload,
            expected_status=expected_status,
            **kwargs,
        )


class StorageS3(ApiClient):
    def __init__(self, url: str, session=None):
        # Передаем сессию, если она указана
        super().__init__(auth_token=None, base_url=url, session=session)
        self.base_url = url

    def upload(self, file_path: str):
        mime_type, _ = mimetypes.guess_type(file_path)
        if mime_type is None:
            mime_type = "application/octet-stream"
        with open(file_path, "rb") as f:
            files = {"file": (os.path.basename(file_path), f, mime_type)}
            return self._put(files=files)

    def download(self):
        return self._get(path="")
