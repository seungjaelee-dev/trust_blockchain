"""학습/개발용 SlithIR 관찰 도구. 판정에는 출력 문자열을 사용하지 않는다."""
from pathlib import Path
import sys
import inspect
from slither.slither import Slither

if sys.argv[1] == "--api":
    from slither.core.cfg.node import Node
    from slither.core.cfg.scope import Scope
    from slither.core.declarations.function import Function
    from slither.core.solidity_types.mapping_type import MappingType
    from slither.slithir.operations import TypeConversion, Binary, LowLevelCall, Unpack
    from slither.core.declarations.contract import Contract
    for cls, names in ((Node, ("__init__", "sons")), (Scope, ()),
                       (Function, ("entry_point", "is_constructor_variables", "payable", "is_implemented")),
                       (MappingType, ("type_from", "type_to")),
                       (TypeConversion, ("variable",)), (Binary, ("type",)),
                       (LowLevelCall, ("function_name", "destination", "call_value", "call_gas")),
                       (Unpack, ("tuple", "index")),
                       (Contract, ("functions", "inheritance"))):
        print(inspect.getfile(cls))
        if not names:
            print(inspect.getsource(cls))
        for name in names:
            member = getattr(cls, name)
            print(inspect.getsource(member.fget if isinstance(member, property) else member))
    raise SystemExit(0)

analysis = Slither(str(Path(sys.argv[1]).resolve()), solc=str(
    Path.home() / ".solc-select/artifacts/solc-0.8.20/solc-0.8.20"))
for contract in analysis.contracts:
    print("CONTRACT", contract.name, "inheritance", contract.inheritance)
    print(" SOURCE", vars(contract.source_mapping.filename))
    print(" DEPLOYMENT", {key: getattr(contract, key) for key in dir(contract)
                         if "abstract" in key or "fully_implemented" in key})
    for variable in contract.state_variables:
        print("STATE", variable.name, type(variable.type).__name__, variable.type,
              "constant", variable.is_constant, "expression", variable.expression)
    for function in contract.functions + contract.modifiers:
        print("FUNCTION", function.name, "constructor", function.is_constructor,
              "visibility", function.visibility, "implemented", function.is_implemented,
              "initialization", function.is_constructor_variables, "modifiers", function.modifiers)
        for node in function.nodes:
            print(" NODE", node.node_id, node.type, node.source_mapping.lines,
                  "sons", [n.node_id for n in node.sons])
            for ir in node.irs:
                print("  IR", type(ir).__name__, str(ir))
                for key in ("lvalue", "rvalue", "variable_left", "variable_right", "type",
                            "function", "arguments", "value", "values"):
                    if hasattr(ir, key):
                        value = getattr(ir, key)
                        print("   ", key, type(value).__name__, str(value))
