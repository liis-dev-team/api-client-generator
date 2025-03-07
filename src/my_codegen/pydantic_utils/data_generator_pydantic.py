import random
from datetime import datetime, date, timedelta
from enum import Enum
from typing import (
    Any, List, Dict, Union, Set,
    get_args, get_origin, ForwardRef, Annotated
)
from uuid import UUID, uuid4

from faker import Faker

from my_codegen.pydantic_utils.pydantic_config import BaseConfigModel

from pydantic import Field, StringConstraints, RootModel

fake = Faker()


class RandomValueGenerator:
    @staticmethod
    def random_value(field_type: Any, current_depth: int = 0, max_depth: int = 3) -> Any:
        origin = get_origin(field_type)
        args = get_args(field_type)

        # 1) Union[Something, None]
        if origin is Union and type(None) in args:
            for arg in args:
                if arg is not type(None):
                    return RandomValueGenerator.random_value(arg, current_depth, max_depth)

        # 2) Union (без None)
        if origin is Union:
            chosen = random.choice(args)
            return RandomValueGenerator.random_value(chosen, current_depth, max_depth)

        # 3) Annotated
        # Проверяем, что это действительно Annotated (или "AnnotatedValue")
        if origin is Annotated or "AnnotatedValue" in str(origin) or "Annotated" in str(origin):
            base_type = args[0] if args else str
            metadata = args[1:] if len(args) > 1 else ()
            return RandomValueGenerator._handle_annotated(
                base_type, metadata, current_depth, max_depth
            )

        # 4) Any
        if field_type is Any:
            return random.choice([fake.word(), random.randint(1, 1000), random.uniform(1.0, 100.0)])

        # 5) Примитивы
        if field_type is str:
            return fake.text(max_nb_chars=20)
        if field_type is int:
            return random.randint(1, 1000)
        if field_type is float:
            return random.uniform(1.0, 100.0)
        if field_type is bool:
            return random.choice([True, False])

        # 6) datetime/date
        if field_type is datetime:
            return (datetime.now() + timedelta(days=1)).isoformat() + "Z"
        if field_type is date:
            return (datetime.now() + timedelta(days=1)).date().isoformat()

        # 7) UUID
        if field_type is UUID:
            return str(uuid4())

        # 8) Контейнеры (List, Dict, Set и т.д.)
        if origin in (list, List):
            if current_depth >= max_depth:
                return []
            return [
                RandomValueGenerator.random_value(args[0], current_depth + 1, max_depth)
                for _ in range(random.randint(1, 2))
            ]
        if origin in (dict, Dict):
            if current_depth >= max_depth:
                return {}
            return {
                fake.word(): RandomValueGenerator.random_value(args[1], current_depth + 1, max_depth)
                for _ in range(random.randint(1, 2))
            }
        if origin in (set, Set):
            if current_depth >= max_depth:
                return set()
            return {
                RandomValueGenerator.random_value(args[0], current_depth + 1, max_depth)
                for _ in range(random.randint(1, 2))
            }

        # 9) Enum
        if isinstance(field_type, type) and issubclass(field_type, Enum):
            return random.choice(list(field_type))

        # 9.1) Если это Pydantic RootModel
        if isinstance(field_type, type) and issubclass(field_type, RootModel):
            root_annotation = field_type.model_fields["root"].annotation
            generated = RandomValueGenerator.random_value(root_annotation, current_depth, max_depth)
            return field_type.model_construct(root=generated, _fields_set={"root"})

        # if isinstance(field_type, type) and issubclass(field_type, RootModel):
        #     root_annotation = field_type.model_fields["root"].annotation
        #     return RandomValueGenerator.random_value(root_annotation, current_depth, max_depth)


        # 10) Обрабатываем Pydantic-модель (ваш BaseConfigModel или BaseModel)
        if isinstance(field_type, type) and issubclass(field_type, BaseConfigModel):
            if current_depth >= max_depth:
                return None
            from_data = GenerateData(field_type, current_depth + 1, max_depth)
            return from_data.fill_all_fields().build()

        # 11) ForwardRef
        if isinstance(field_type, ForwardRef):
            return []

        # 12) Ничего не подошло
        raise ValueError(f"Unsupported field type: {field_type}")

    @staticmethod
    def _handle_annotated(base_type: Any, metadata: tuple, current_depth: int, max_depth: int) -> Any:
        if base_type is str:
            min_len = 1
            max_len = 20
            for meta in metadata:
                if isinstance(meta, Field):
                    if meta.min_length is not None:
                        min_len = meta.min_length
                    if meta.max_length is not None:
                        max_len = meta.max_length
                elif isinstance(meta, StringConstraints):
                    if meta.min_length is not None:
                        min_len = meta.min_length
                    if meta.max_length is not None:
                        max_len = meta.max_length

            length = random.randint(min_len, max_len) if min_len <= max_len else 1
            return fake.pystr(min_chars=length, max_chars=length)

        # Если это Annotated[int], Annotated[float] и т.д., используем общую логику
        return RandomValueGenerator.random_value(base_type, current_depth, max_depth)


class GenerateData:
    def __init__(
            self,
            model_class: type[BaseConfigModel],
            current_depth: int = 0,
            max_depth: int = 3,
    ):
        self.model_class = model_class
        self.data = {}
        self.current_depth = current_depth
        self.max_depth = max_depth

    def _fill_fields(self, required_only: bool = False, optional_only: bool = False):
        """
        Заполняет поля модели (обязательные/опциональные).
        """
        fields = self.model_class.model_fields

        for field_name, field_info in fields.items():
            # Если поле уже заполнено вручную — пропускаем
            if field_name in self.data:
                continue

            annotation = field_info.annotation
            origin = get_origin(annotation)
            args = get_args(annotation)

            is_union = (origin is Union)
            is_optional = is_union and (type(None) in args)

            # Пропускаем, если не соответствует режиму (только обязательные / только опциональные)
            if required_only and is_optional:
                continue
            if optional_only and not is_optional:
                continue

            # Если Optional[...] -> достаём реальный тип
            if is_optional:
                real_type = next(a for a in args if a is not type(None))
            else:
                real_type = annotation

            # Генерируем значение
            self.data[field_name] = RandomValueGenerator.random_value(
                real_type,
                current_depth=self.current_depth,
                max_depth=self.max_depth,
            )

    def fill_all_fields(self, **data):
        self.data.update(data)
        self._fill_fields(required_only=False, optional_only=False)
        return self

    def fill_required(self, **data):
        self.data.update(data)
        self._fill_fields(required_only=True, optional_only=False)
        return self

    def fill_optional(self, **data):
        self.data.update(data)
        self._fill_fields(required_only=False, optional_only=True)
        return self

    def set_field(self, **kwargs):
        self.data.update(kwargs)
        return self

    def build(self):
        """
        Создаёт модель pydantic v2 без валидации (аналогично старому .construct).
        """
        return self.model_class.model_construct(_validate=False, **self.data)

    def to_dict(self):
        """
        Рекурсивно приводит итоговый объект (BaseConfigModel) к словарю.
        """
        return self._convert_to_dict(self.build())

    def _convert_to_dict(self, instance: BaseConfigModel):
        if isinstance(instance, BaseConfigModel):
            result = {}
            for k, v in instance.__dict__.items():
                if isinstance(v, BaseConfigModel):
                    result[k] = self._convert_to_dict(v)
                elif isinstance(v, list):
                    result[k] = [self._convert_to_dict(i) for i in v]
                elif isinstance(v, dict):
                    result[k] = {kk: self._convert_to_dict(vv) for kk, vv in v.items()}
                else:
                    result[k] = v
            return result
        return instance

