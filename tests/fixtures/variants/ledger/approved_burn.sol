// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

contract Benign015V4 {
    uint256 public totalSupply;
    mapping(address => uint256) public balanceOf;
    mapping(address => mapping(address => uint256)) public burnAllowance;

    constructor(uint256 supply) {
        totalSupply = supply;
        balanceOf[msg.sender] = supply;
    }

    function approveBurn(address operator, uint256 amount) external {
        burnAllowance[msg.sender][operator] = amount;
    }

    function burnFrom(address from, uint256 amount) external {
        require(balanceOf[from] >= amount, "balance");
        require(burnAllowance[from][msg.sender] >= amount, "allowance");
        burnAllowance[from][msg.sender] -= amount;
        balanceOf[from] -= amount;
        totalSupply -= amount;
    }
}
