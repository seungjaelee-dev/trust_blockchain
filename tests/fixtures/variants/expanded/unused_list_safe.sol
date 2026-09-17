// SPDX-License-Identifier: MIT






pragma solidity ^0.8.20;

contract RewardPool {
    string public name = "RewardPool";
    string public symbol = "RWP";
    uint8  public constant decimals = 18;
    uint256 public totalSupply;
    address public owner;
    mapping(address => uint256) public balanceOf;
    mapping(address => bool)    public whitelist;

    event Transfer(address indexed from, address indexed to, uint256 value);

    constructor(uint256 initialSupply) {
        owner = msg.sender;
        totalSupply = initialSupply;
        balanceOf[msg.sender] = initialSupply;
        whitelist[msg.sender] = true;
        emit Transfer(address(0), msg.sender, initialSupply);
    }

    modifier onlyOwner() { require(msg.sender == owner, "not owner"); _; }

    function setWhitelist(address account, bool allowed) external onlyOwner {
        whitelist[account] = allowed;
    }

    
    function transfer(address to, uint256 value) external returns (bool) {

        require(to != address(0), "zero address");
        require(balanceOf[msg.sender] >= value, "insufficient");
        balanceOf[msg.sender] -= value;
        balanceOf[to] += value;
        emit Transfer(msg.sender, to, value);
        return true;
    }
}
