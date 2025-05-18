import inspect
import degirum as dg

def get_function_parameters(func):
    signature = inspect.signature(func)
    params_info = []

    for param in signature.parameters.values():
        param_info = {
            'name': param.name,
            'kind': param.kind.name,
            'has_default': param.default is not inspect.Parameter.empty,
            'default': None if param.default is inspect.Parameter.empty else param.default
        }
        params_info.append(param_info)

    return params_info


if __name__ == "__main__":
    params_info = get_function_parameters(dg.load_model)

    for param in params_info:
        print(f"Parameter: {param['name']}, Kind: {param['kind']}, Has Default: {param['has_default']}, Default: {param['default']}")