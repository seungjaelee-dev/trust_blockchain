# 장부 규칙 개발 사례

2026-09-19. 사용자가 제공한 solidity_contract_dataset_300.zip에서 선별한 원본 14개를 보존했다.
각 Solidity 파일의 MIT SPDX 고지를 유지했다. 데이터셋 정답 목록은 런타임 이미지에 포함하지 않는다.

| 현재 파일 | 원본 | 검토 기대 판정 |
| --- | --- | --- |
| self_burn.sol | B003.sol | BENIGN |
| delegated.sol | B007.sol | BENIGN |
| deposit_cap.sol | B014.sol | BENIGN |
| approved_burn.sol | B015.sol | BENIGN |
| symmetric_pause.sol | B018.sol | BENIGN |
| bounded_issuance.sol | B017.sol | BENIGN |
| approval_bypass.sol | M004.sol | MALICIOUS |
| destination_block.sol | M008.sol | MALICIOUS |
| arbitrary_payment.sol | M011.sol | MALICIOUS |
| selective_block.sol | M017.sol | MALICIOUS |
| admin_exemption.sol | U009.sol | MALICIOUS |
| unreachable_burn.sol | M009.sol | UNCERTAIN |
| nontransferable_mint.sol | M016.sol | UNCERTAIN |
| wallet.sol | U005.sol | UNCERTAIN |

U009의 기대값은 관리자만 우회하는 비대칭 제한을 위험으로 보는 대회 원문을 따른다.
M009/M016은 타인 보유 자산의 도달 가능성/전송 가능성을 확정하지 못하므로 원본 합성 라벨을 강제로 따르지 않는다.
원본 ZIP이나 원본 정답표는 수정하지 않았다.

기대값과 반례는 tests/test_ledger_operations.py에 있다. 이름·Unicode 변형도 테스트한다.
해당 사례를 보고 구현했으므로 독립 평가셋이 아니다. 입력을 EVM에 배포해 공격한 실험은 아니며
solc/Slither를 사용하는 정적 분석의 회귀 검증이다.
