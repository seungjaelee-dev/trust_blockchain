// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

contract Benign018V2 {
    address public guardian;
    bool public paused;
    mapping(address => uint256) public balanceOf;

    constructor(uint256 supply) {
        guardian = msg.sender;
        balanceOf[msg.sender] = supply;
    }
    modifier onlyGuardian() { require(msg.sender == guardian, "guardian"); _; }

    function setPaused(bool value) external onlyGuardian { paused = value; }

    function transfer(address to, uint256 amount) external {
        require(!paused, "paused");
        require(balanceOf[msg.sender] >= amount, "balance");
        balanceOf[msg.sender] -= amount;
        balanceOf[to] += amount;
    }
}
