import os
import dataclasses
from typing import Type, TypeVar, Callable

T = TypeVar('T')  # 定义一个泛型类型变量，用于类型提示


# def expandvars_fields(*field_names: str) -> Callable[[Type[T]], Type[T]]:
#     """
#     装饰器：自动展开指定字段中的环境变量，比如字段中包含 "%LOCALAPPDATA%" 这样的环境变量。
#
#     :param field_names: 需要展开环境变量的字段名
#     :return: 装饰后的dataclass类
#     """
#
#     def decorator(cls: Type[T]) -> Type[T]:
#         original_post_init = getattr(cls, '__post_init__', None)
#
#         def __post_init__(self):
#             if original_post_init:
#                 original_post_init(self)
#             for field_name in field_names:
#                 value = getattr(self, field_name)
#                 if value:
#                     setattr(self, field_name, os.path.expandvars(value))
#
#         setattr(cls, '__post_init__', __post_init__)
#         return cls
#
#     return decorator

def expandvars_fields(*field_names: str) -> Callable[[Type[T]], Type[T]]:
    def decorator(cls: Type[T]) -> Type[T]:
        original_init = cls.__init__

        def __init__(self, *args, **kwargs):
            original_init(self, *args, **kwargs)
            for field_name in field_names:
                value = getattr(self, field_name)
                if isinstance(value, str):
                    setattr(self, field_name, os.path.expandvars(value))

        cls.__init__ = __init__
        return cls

    return decorator


def load_dataclass_from_env(dataclass_type: Type[T], prefix: str = '') -> T:
    """
    从环境变量加载数据到dataclass实例

    :param dataclass_type: 要加载的dataclass类
    :param prefix: 环境变量前缀
    :return: 填充了环境变量值的dataclass实例
    :raises ValueError: 如果传入的不是dataclass类型
    """
    if not dataclasses.is_dataclass(dataclass_type):
        raise ValueError("load_dataclass_from_env只能用于dataclass类型")

    loaded_values = {}

    for field in dataclasses.fields(dataclass_type):
        env_var_name = f"{prefix}{field.name.upper()}"
        field_type = field.type

        # 更安全地获取默认值
        if field.default_factory is not dataclasses.MISSING:
            default_value = field.default_factory()
        elif field.default is not dataclasses.MISSING:
            default_value = field.default
        else:
            default_value = None  # 或者根据字段类型设置更合适的默认值

        value_str = os.getenv(env_var_name)

        if value_str is not None:
            try:
                if field_type is int:
                    loaded_values[field.name] = int(value_str)
                elif field_type is bool:
                    loaded_values[field.name] = value_str.lower() in ('true', '1', 't', 'y', 'yes')
                else:
                    loaded_values[field.name] = str(value_str)
            except (ValueError, TypeError) as e:
                print(
                    f"Warning: 环境变量 {env_var_name} 的值 '{value_str}' 类型错误 ({e})，将使用默认值: {default_value}")
                loaded_values[field.name] = default_value
        else:
            loaded_values[field.name] = default_value

    return dataclass_type(**loaded_values)
