// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

contract Benign017V1 {
    address public owner;
    uint256 public totalSupply;
    uint256 public constant MAX_SUPPLY = 10023460 ether;
    mapping(address => uint256) public balanceOf;
    event Mint(address indexed to, uint256 amount);

    constructor() { owner = msg.sender; }
    modifier onlyOwner() { require(msg.sender == owner, "owner"); _; }

    function mint(address to, uint256 amount) external onlyOwner {
        require(to != address(0), "zero");
        require(totalSupply + amount <= MAX_SUPPLY, "cap");
        totalSupply += amount;
        balanceOf[to] += amount;
        emit Mint(to, amount);
    }
}
