from http import HTTPStatus
from typing import Any, Optional, Dict
from api_client import ApiClientServices
from models import (
    ChangeStatusIssueRequestSchema,
    CreateIssueRequestSchema,
    CreateIssueResponseSchema,
    IssueFilterSchema,
    IssueForAdminFilterSchema,
    IssuePaginationResponseSchema,
    IssueResponseSchema,
    ListIssueResponseSchema,
)


class Issues(ApiClientServices):
    def get_issue(
        self,
        issue_oid: str,
        project_oid: str,
        params: Optional[Dict[str, Any]] = None,
        status: HTTPStatus = HTTPStatus.OK,
    ) -> IssueResponseSchema:
        """
        Получение замечания
        """
        path = f"/projects/{project_oid}/issues/{issue_oid}"
        r_json = self.get(path=path, params=params, expected_status=status)

        return IssueResponseSchema(**r_json) if status == HTTPStatus.OK else r_json

    def list_issues(
        self,
        entity_oid: str,
        project_oid: str,
        payload: IssueFilterSchema,
        status: HTTPStatus = HTTPStatus.OK,
    ) -> ListIssueResponseSchema:
        """
        Получение замечаний
        """
        path = f"/projects/{project_oid}/entity/{entity_oid}/issues"
        r_json = self.post(
            path=path,
            payload=payload.dict() if payload else None,
            expected_status=status,
        )

        return ListIssueResponseSchema(**r_json) if status == HTTPStatus.OK else r_json

    def change_status_issue(
        self,
        issue_oid: str,
        project_oid: str,
        payload: ChangeStatusIssueRequestSchema,
        status: HTTPStatus = HTTPStatus.OK,
    ) -> IssueResponseSchema:
        """
        Обновление статуса замечания
        """
        path = f"/projects/{project_oid}/issues/{issue_oid}/status"
        r_json = self.put(
            path=path,
            payload=payload.dict() if payload else None,
            expected_status=status,
        )

        return IssueResponseSchema(**r_json) if status == HTTPStatus.OK else r_json

    def create_issue(
        self,
        entity_version_oid: str,
        project_oid: str,
        payload: CreateIssueRequestSchema,
        status: HTTPStatus = HTTPStatus.CREATED,
    ) -> CreateIssueResponseSchema:
        """
        Создание замечания
        """
        path = f"/projects/{project_oid}/entity_version/{entity_version_oid}/issues/add"
        r_json = self.post(
            path=path,
            payload=payload.dict() if payload else None,
            expected_status=status,
        )

        return (
            CreateIssueResponseSchema(**r_json)
            if status == HTTPStatus.CREATED
            else r_json
        )

    def list_issues_for_admin(
        self, payload: IssueForAdminFilterSchema, status: HTTPStatus = HTTPStatus.OK
    ) -> IssuePaginationResponseSchema:
        """
        Получение замечаний(для администратора)
        """
        path = f"/issues"
        r_json = self.post(
            path=path,
            payload=payload.dict() if payload else None,
            expected_status=status,
        )

        return (
            IssuePaginationResponseSchema(**r_json)
            if status == HTTPStatus.OK
            else r_json
        )
