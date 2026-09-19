// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

contract Uncertain005V4 {
    address public owner;
    constructor() { owner = msg.sender; }
    modifier onlyOwner() { require(msg.sender == owner, "owner"); _; }
    receive() external payable {}

    function execute(address target, uint256 value, bytes calldata data)
        external onlyOwner returns (bytes memory)
    {
        (bool ok, bytes memory result) = target.call{value: value}(data);
        require(ok, "call");
        return result;
    }
}
