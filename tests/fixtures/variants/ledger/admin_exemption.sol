// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

contract Uncertain009V3 {
    address public admin;
    bool public paused;
    mapping(address => uint256) public balanceOf;
    constructor(uint256 supply) {
        admin = msg.sender;
        balanceOf[msg.sender] = supply;
    }
    modifier onlyAdmin() { require(msg.sender == admin, "admin"); _; }

    function setPaused(bool value) external onlyAdmin { paused = value; }

    function transfer(address to, uint256 amount) external {
        require(!paused || msg.sender == admin, "paused");
        require(balanceOf[msg.sender] >= amount, "balance");
        balanceOf[msg.sender] -= amount;
        balanceOf[to] += amount;
    }
}
