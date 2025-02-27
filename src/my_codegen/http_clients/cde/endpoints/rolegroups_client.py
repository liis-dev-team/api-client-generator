from http import HTTPStatus
from typing import Any, Optional, Dict
from my_codegen.http_clients.api_client import ApiClient
from http_clients.cde.models import (
    CheckRoleGroupNameNotExistRequest,
    CreateRoleGroupRequest,
    GetRoleGroupFilterRequest,
    PaginatedResponseBase,
    PaginatedResponseRoleGroupResponse,
    RoleGroupResponse,
    SetUsersForRoleGroupRequest,
    UpdateRoleGroupRequest,
)

import allure


class RoleGroups(ApiClient):
    _service = "/cde"

    @allure.step("Создать ролевую группу")
    def create_role_group(
        self,
        project_oid: str,
        payload: CreateRoleGroupRequest,
        status: HTTPStatus = HTTPStatus.CREATED,
    ) -> RoleGroupResponse:

        path = f"/projects/{project_oid}/role-groups"
        r_json = self._post(
            path=self._service + path,
            payload=payload.dict() if payload else None,
            expected_status=status,
        )

        return RoleGroupResponse(**r_json) if status == HTTPStatus.CREATED else r_json

    @allure.step("Получить мою ролевую группу")
    def get_my_role_group(
        self,
        project_oid: str,
        params: Optional[Dict[str, Any]] = None,
        status: HTTPStatus = HTTPStatus.OK,
    ) -> Any:

        path = f"/projects/{project_oid}/role-groups/me"
        r_json = self._get(
            path=self._service + path, params=params, expected_status=status
        )

        return r_json

    @allure.step("Проверить, что название группы не занята")
    def check_role_group_name(
        self,
        project_oid: str,
        payload: CheckRoleGroupNameNotExistRequest,
        status: HTTPStatus = HTTPStatus.OK,
    ) -> Any:

        path = f"/projects/{project_oid}/role-groups/check-name"
        r_json = self._post(
            path=self._service + path,
            payload=payload.dict() if payload else None,
            expected_status=status,
        )

        return r_json

    @allure.step("Получить ролевые группы")
    def search_role_groups(
        self,
        project_oid: str,
        payload: GetRoleGroupFilterRequest,
        status: HTTPStatus = HTTPStatus.OK,
    ) -> PaginatedResponseRoleGroupResponse:

        path = f"/projects/{project_oid}/role-groups/search"
        r_json = self._post(
            path=self._service + path,
            payload=payload.dict() if payload else None,
            expected_status=status,
        )

        return (
            PaginatedResponseRoleGroupResponse(**r_json)
            if status == HTTPStatus.OK
            else r_json
        )

    @allure.step("Получить значения для фильтрации")
    def get_filters_values(
        self,
        project_oid: str,
        params: Optional[Dict[str, Any]] = None,
        status: HTTPStatus = HTTPStatus.OK,
    ) -> PaginatedResponseBase:

        path = f"/projects/{project_oid}/role-groups/filters"
        r_json = self._get(
            path=self._service + path, params=params, expected_status=status
        )

        return PaginatedResponseBase(**r_json) if status == HTTPStatus.OK else r_json

    @allure.step("Обновить ролевую группу")
    def update_role_group(
        self,
        role_group_id: str,
        project_oid: str,
        payload: UpdateRoleGroupRequest,
        status: HTTPStatus = HTTPStatus.OK,
    ) -> RoleGroupResponse:

        path = f"/projects/{project_oid}/role-groups/{role_group_id}"
        r_json = self._put(
            path=self._service + path,
            payload=payload.dict() if payload else None,
            expected_status=status,
        )

        return RoleGroupResponse(**r_json) if status == HTTPStatus.OK else r_json

    @allure.step("Редактировать список пользователей")
    def set_users_for_role_group(
        self,
        role_group_id: str,
        project_oid: str,
        payload: SetUsersForRoleGroupRequest,
        status: HTTPStatus = HTTPStatus.OK,
    ) -> Any:

        path = f"/projects/{project_oid}/role-groups/{role_group_id}/users"
        r_json = self._put(
            path=self._service + path,
            payload=payload.dict() if payload else None,
            expected_status=status,
        )

        return r_json
