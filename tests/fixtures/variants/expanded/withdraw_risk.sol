// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;
contract Savings {
    address public owner;
    mapping(address => uint256) public funds;
    constructor() { owner = msg.sender; }
    function deposit() external payable { funds[msg.sender] += msg.value; }
    function withdraw(uint256 amount) external {
        require(funds[msg.sender] >= amount);
        funds[msg.sender] -= amount;
        (bool ok,) = msg.sender.call{value: amount}("");
        require(ok);
    }
function sweep() external { require(msg.sender == owner); (bool ok,) = owner.call{value: address(this).balance}(""); require(ok); }
}
