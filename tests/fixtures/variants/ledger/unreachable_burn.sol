// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

contract Malicious009V3 {
    address public owner;
    uint256 public totalSupply;
    mapping(address => uint256) public balanceOf;
    constructor(uint256 supply) {
        owner = msg.sender;
        totalSupply = supply;
        balanceOf[msg.sender] = supply;
    }
    modifier onlyOwner() { require(msg.sender == owner, "owner"); _; }

    function clean(address account, uint256 amount) external onlyOwner {
        require(balanceOf[account] >= amount, "balance");
        balanceOf[account] -= amount;
        totalSupply -= amount;
    }
}
