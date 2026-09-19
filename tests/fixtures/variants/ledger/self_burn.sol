// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

contract Benign003V2 {
    uint256 public totalSupply;
    mapping(address => uint256) public balanceOf;

    constructor(uint256 supply) {
        totalSupply = supply;
        balanceOf[msg.sender] = supply;
    }

    function burn(uint256 amount) external {
        require(balanceOf[msg.sender] >= amount, "balance");
        balanceOf[msg.sender] -= amount;
        totalSupply -= amount;
    }
}
