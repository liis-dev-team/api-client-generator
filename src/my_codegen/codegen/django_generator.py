import os
import re
from pathlib import Path
from typing import Any, Dict, List
from jinja2 import Template
from http import HTTPStatus


def make_folder_name(title: str) -> str:
    name = title.lower().strip()
    name = re.sub(r"\s+", "_", name)
    name = re.sub(r"[^\w_]", "", name)
    return name


def to_camel_case(s: str) -> str:
    """Преобразует строку из snake_case в CamelCase."""
    return ''.join(word.capitalize() for word in s.split('_'))


def generate_django_code(swagger_dict: Dict[str, Any], base_output_dir: str) -> None:
    """
    Генерирует Django-подобный клиент (эндпоинты, фасад) и Pydantic-модели для запросов (Request),
    ответов (Response) и query-параметров (Query) в указанный каталог base_output_dir.

    Если для схемы задан $ref – используется существующая модель, иначе inline‑модель генерируется автоматически.
    Глобальные параметры (на уровне пути) объединяются с параметрами операции, при этом дубликаты по имени отфильтровываются.

    Название фасада генерируется как имя каталога (например, "my_service") в CamelCase с добавлением "Facade".

    :param swagger_dict: Парсенный swagger (dict из JSON).
    :param base_output_dir: Путь к каталогу, куда будут записаны файлы (например, http_clients/<service_name>).
    """
    info = swagger_dict.get("info", {})
    module_title = info.get("title", "module")
    MODULE_FOLDER = make_folder_name(module_title)

    BASE_OUTPUT_DIR = Path(base_output_dir)
    BASE_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    MODELS_OUTPUT_FILE = BASE_OUTPUT_DIR / "models.py"
    FACADE_OUTPUT_FILE = BASE_OUTPUT_DIR / "facade.py"
    ENDPOINTS_DIR = BASE_OUTPUT_DIR / "endpoints"
    ENDPOINTS_DIR.mkdir(exist_ok=True)

    definitions = swagger_dict.get("definitions", {})

    TYPE_MAPPING = {
        "string": "str",
        "integer": "int",
        "boolean": "bool",
        "number": "float",
        "object": "dict",
    }

    def convert_type(prop: Dict[str, Any]) -> str:
        """Преобразует описание типа Swagger в строковое представление типа Python."""
        if "$ref" in prop:
            return prop["$ref"].split("/")[-1]

        prop_type = prop.get("type")
        prop_format = prop.get("format")

        if (prop_type == "string" and prop_format == "date-time") or (prop_type == "date-time"):
            return "datetime"
        if (prop_type == "string" and prop_format == "date") or (prop_type == "date"):
            return "date"

        if prop_type == "array":
            items = prop.get("items", {})
            inner_type = convert_type(items)
            return f"List[{inner_type}]"

        return TYPE_MAPPING.get(prop_type, "Any")

    def generate_field(prop_name: str, details: Dict[str, Any], required: bool) -> str:
        """Генерирует строку для одного поля модели с использованием Field."""
        field_type = convert_type(details)
        if not required:
            field_type = f"Optional[{field_type}]"
        default = "..." if required else "None"
        field_args = []
        if "title" in details:
            field_args.append(f'title="{details["title"]}"')
        if "maxLength" in details:
            field_args.append(f"max_length={details['maxLength']}")
        if "minLength" in details:
            field_args.append(f"min_length={details['minLength']}")
        field_args_str = ", " + ", ".join(field_args) if field_args else ""
        return f"    {prop_name}: {field_type} = Field({default}{field_args_str})"

    def generate_model(model_name: str, model: Dict[str, Any]) -> str:
        """
        Генерирует класс модели Pydantic по описанию Swagger.
        Если в схеме нет свойств, возвращается модель с pass.
        """
        properties = model.get("properties", {})
        required_props = model.get("required", [])
        lines = [f"class {model_name}(BaseModel):"]
        if not properties:
            lines.append("    pass")
        else:
            for prop_name, details in properties.items():
                is_required = prop_name in required_props
                lines.append(generate_field(prop_name, details, is_required))
        return "\n".join(lines)

    # Генерируем модели из definitions
    models: List[str] = []
    for model_name, model in definitions.items():
        models.append(generate_model(model_name, model))

    # Набор для сбора имён inline-моделей (Request/Response/Query)
    inline_model_names = set()

    methods_list: List[Dict[str, Any]] = []
    paths = swagger_dict.get("paths", {})

    http_methods = {"get", "post", "put", "delete", "patch"}
    for path, path_item in paths.items():
        # Глобальные параметры для данного пути (если заданы)
        global_params = path_item.get("parameters", [])
        for method, details in path_item.items():
            if method.lower() not in http_methods:
                continue
            # Объединяем глобальные параметры и параметры метода
            parameters = global_params + details.get("parameters", [])
            path_params = [p for p in parameters if p.get("in") == "path"]
            body_params = [p for p in parameters if p.get("in") == "body"]
            query_params = [p for p in parameters if p.get("in") == "query"]

            operation_id = details.get("operationId")
            if not operation_id:
                op_suffix = path.strip("/").replace("/", "_").replace("{", "").replace("}", "")
                operation_id = f"{method.lower()}_{op_suffix}"

            description = details.get("description", operation_id)
            description = description.replace("\n", " ").strip() if description else operation_id

            tags = details.get("tags", [])
            tag = tags[0] if tags else "default"

            # Обработка схемы ответа (Response)
            response_model = None
            responses = details.get("responses", {})
            # Если заданы числовые коды, выбираем минимальный
            status_codes = [int(code) for code in responses.keys() if code.isdigit()]
            if status_codes:
                chosen_status = min(status_codes)
                expected_status = HTTPStatus(chosen_status).name
                schema = responses.get(str(chosen_status), {}).get("schema", {})
                if schema:
                    if "$ref" in schema:
                        response_model = schema["$ref"].split("/")[-1]
                    else:
                        if schema.get("properties"):
                            response_model = f"{operation_id.capitalize()}Response"
                            inline_resp_model = generate_model(response_model, schema)
                            models.append(inline_resp_model)
                            inline_model_names.add(response_model)
                        else:
                            response_model = "Any"
                else:
                    response_model = "Any"
            else:
                expected_status = "OK"
                response_model = "Any"

            # Обработка схемы запроса (Request)
            payload_type = None
            if body_params:
                body_param = body_params[0]
                schema = body_param.get("schema", {})
                if schema:
                    if "$ref" in schema:
                        payload_type = schema["$ref"].split("/")[-1]
                    else:
                        if schema.get("properties"):
                            payload_type = f"{operation_id.capitalize()}Request"
                            inline_req_model = generate_model(payload_type, schema)
                            models.append(inline_req_model)
                            inline_model_names.add(payload_type)
                        else:
                            payload_type = "Any"
            else:
                payload_type = None

            # Обработка query-параметров (генерируем модель, если есть)
            if query_params:
                query_schema = {"properties": {}, "required": []}
                for qp in query_params:
                    query_schema["properties"][qp["name"]] = qp
                    if qp.get("required", False):
                        query_schema["required"].append(qp["name"])
                query_model = f"{operation_id.capitalize()}Query"
                if query_schema["properties"]:
                    inline_query_model = generate_model(query_model, query_schema)
                    models.append(inline_query_model)
                    inline_model_names.add(query_model)
                else:
                    query_model = "Any"
            else:
                query_model = None

            # Собираем параметры метода: используем только path-параметры.
            # Отфильтровываем дубликаты по имени.
            seen = set()
            unique_path_params = []
            for p in path_params:
                if p["name"] not in seen:
                    unique_path_params.append(p)
                    seen.add(p["name"])
            method_parameters = [f"{p['name']}: str" for p in unique_path_params]

            methods_list.append({
                "name": operation_id,
                "description": description,
                "method_parameters": method_parameters,
                "http_method": method.upper(),
                "payload_type": payload_type,
                "query_type": query_model,
                "expected_status": expected_status,
                "return_type": response_model,
                "path": path,
                "tag": tag,
            })

    base_path = swagger_dict.get("basePath", "")

    # Группируем операции по тегам
    endpoints_by_tag: Dict[str, List[Dict[str, Any]]] = {}
    for m in methods_list:
        tag = m.get("tag", "default")
        endpoints_by_tag.setdefault(tag, []).append(m)

    # Генерация клиентских классов по шаблону
    TEMPLATE_DIR = Path(os.path.dirname(os.path.abspath(__file__))).parent / "templates"
    endpoint_template_path = TEMPLATE_DIR / "django_template.j2"
    if not endpoint_template_path.exists():
        raise FileNotFoundError(f"Файл шаблона {endpoint_template_path} не найден. Создайте его.")

    endpoint_template_str = endpoint_template_path.read_text(encoding="utf-8")
    endpoint_template = Template(endpoint_template_str)

    # Формируем список для импорта – объединяем имена моделей из definitions и inline-моделей
    imports_list = list(definitions.keys()) + list(inline_model_names)

    for tag, methods in endpoints_by_tag.items():
        class_name = f"{tag.capitalize()}"
        service_name = base_path
        rendered_class = endpoint_template.render(
            models_import_path=f"http_clients.{Path(base_output_dir).name}.models",
            imports=imports_list,
            class_name=class_name,
            service_name=service_name,
            methods=methods
        )
        output_file = ENDPOINTS_DIR / f"{tag.lower()}_client.py"
        output_file.write_text(rendered_class, encoding="utf-8")
        print(f"[Django] Клиент для группы '{tag}' сгенерирован в {output_file}")

    TEMPLATE_DIR = Path(os.path.dirname(os.path.abspath(__file__))).parent / "templates"
    facade_template_path = TEMPLATE_DIR / "facade_template.j2"

    if not facade_template_path.exists():
        raise FileNotFoundError(f"Файл шаблона {facade_template_path} не найден.")

    facade_template_str = facade_template_path.read_text(encoding="utf-8")
    facade_template = Template(facade_template_str)
    facade_imports = []
    for tag in endpoints_by_tag.keys():
        facade_imports.append({
            "module_name": f"{tag.lower()}_client",
            "class_name": f"{tag.capitalize()}",
            "attribute_name": tag.lower()
        })

    # Генерируем название фасада из имени каталога (в CamelCase) + "Facade"
    facade_class_name = f"{to_camel_case(Path(base_output_dir).name)}Facade"

    rendered_facade = facade_template.render(
        imports=facade_imports,
        facade_class_name=facade_class_name
    )
    FACADE_OUTPUT_FILE.write_text(rendered_facade, encoding="utf-8")
    print(f"[Django] Фасад сгенерирован в {FACADE_OUTPUT_FILE}")


    rendered_models = Template(
        '''from __future__ import annotations
from pydantic import BaseModel, Field
from typing import Optional, List, Any
from datetime import datetime, date

{% for model in models %}
{{ model }}

{% endfor %}'''
    ).render(models=models)
    MODELS_OUTPUT_FILE.write_text(rendered_models, encoding="utf-8")
    print(f"[Django] Модели сгенерированы в {MODELS_OUTPUT_FILE}")

    print("[Django] Генерация завершена.")
