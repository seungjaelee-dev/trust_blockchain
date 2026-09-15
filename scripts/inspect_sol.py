"""학습용 구조 출력. 판정기나 대회 JSON 진입점이 아니다."""

import argparse
from pathlib import Path
import sys

from slither.slither import Slither


def print_nodes(nodes):
    """노드 목록을 표시한다. 출력 순서가 실행 순서라는 뜻은 아니다."""
    for node in nodes:
        print("   ", node.source_mapping.lines, node.type.name, node.expression)


def inspect_file(path):
    """소스 하나를 읽어 함수와 modifier 구조를 출력한다."""
    analysis = Slither(str(path.resolve()))
    print("FILE:", path.name)

    for contract in analysis.contracts:
        print("CONTRACT:", contract.name)

        for function in contract.functions:
            print("  FUNCTION:", function.name)
            if function.is_constructor_variables:
                print("    [Slither internal variable initialization]")
            print("    MODIFIERS:", [item.name for item in function.modifiers])
            print_nodes(function.nodes)

        # modifier 정의는 따로 출력한다. 상속 생성자 호출과 혼동하지 않는다.
        for modifier in contract.modifiers:
            print("  MODIFIER DEFINITION:", modifier.name)
            print_nodes(modifier.nodes)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path, help="읽을 Solidity 파일 경로")
    args = parser.parse_args()

    if args.source.suffix != ".sol" or not args.source.is_file():
        parser.error("존재하는 .sol 파일을 지정하세요.")

    try:
        inspect_file(args.source)
    except Exception as error:
        # 학습용 단일 파일 도구의 오류 정책. 제출용 일괄 CLI는 별도로 구현한다.
        print(f"구조 읽기 실패 ({type(error).__name__}): {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
