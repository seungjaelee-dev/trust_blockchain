// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

contract Malicious017V1 {
    address public owner;
    mapping(address => uint256) public balanceOf;
    mapping(address => bool) public permitted;

    constructor(uint256 supply) {
        owner = msg.sender;
        balanceOf[msg.sender] = supply;
        permitted[msg.sender] = true;
    }
    modifier onlyOwner() { require(msg.sender == owner, "owner"); _; }

    function setTradingState(address user, bool value) external onlyOwner {
        permitted[user] = value;
    }

    function transfer(address to, uint256 amount) external {
        require(permitted[msg.sender], "restricted");
        require(balanceOf[msg.sender] >= amount, "balance");
        balanceOf[msg.sender] -= amount;
        balanceOf[to] += amount;
    }
}
