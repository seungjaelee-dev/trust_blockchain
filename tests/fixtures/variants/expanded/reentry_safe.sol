// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;
contract Savings {
    address public owner;
    mapping(address => uint256) public funds;
    constructor() { owner = msg.sender; }
    function deposit() external payable { funds[msg.sender] += msg.value; }
    function withdraw() external {
        uint256 amount = funds[msg.sender];
        require(amount > 0);
        funds[msg.sender] = 0;
        (bool ok,) = msg.sender.call{value: amount}("");
        require(ok);
    }
}
