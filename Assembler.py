# Define opcodes for different types of instructions
opcodes = {
    "add": "000000", "sub": "000000", "and": "000000", "or": "000000",
    "xor": "000000", "nor": "000000", "slt": "000000", "sltu": "000000",
    "sll": "000000", "srl": "000000", "sra": "000000", "sllv": "000000",
    "srlv": "000000", "srav": "000000", "jr": "000000", "addu": "000000",
    "subu": "000000", "slti": "001010", "sltiu": "001011", "addi": "001000",
    "addiu": "001001", "andi": "001100", "ori": "001101", "xori": "001110",
    "lw": "100011", "sw": "101011", "beq": "000100", "bne": "000101",
    "j": "000010", "jal": "000011"
}

# Define function codes for R-type instructions
func_codes = {
    "add": "100000", "sub": "100010", "and": "100100", "or": "100101",
    "xor": "100110", "nor": "100111", "slt": "101010", "sltu": "101011",
    "sll": "000000", "srl": "000010", "sra": "000011", "sllv": "000100",
    "srlv": "000110", "srav": "000111", "jr": "001000", "addu": "100001",
    "subu": "100011"
}

# Register mapping
registers = {f"${i}": f"{i:05b}" for i in range(32)}
def parse_immediate(value):
    # Check for hexadecimal and parse accordingly
    if value.lower().startswith("0x"):
        return int(value, 16)  # Parse as hexadecimal
    return int(value)  # Parse as decimal
# Parsing function
def parse_instruction(line):
    parts = line.replace(',', ' ').split()
    opcode = parts[0].lower()
    operands = parts[1:]
    return opcode, operands

# Assembling functions for R-type
def assemble_r_type(opcode, operands):
    if opcode in ["sll", "srl", "sra", "sllv", "srlv", "srav"]:
        rd = registers[operands[0]]
        rs = "00000"
        rt = registers[operands[1]]
        shamt = format(int(operands[2]), '05b')
    elif opcode == "jr":
        rs = registers[operands[0]]
        rt = "00000"
        rd = "00000"
        shamt = "00000"
    else:
        rd = registers[operands[0]]
        rs = registers[operands[1]]
        rt = registers[operands[2]]
        shamt = "00000"
    func = func_codes[opcode]
    return f"{opcodes[opcode]}_{rs}_{rt}_{rd}_{shamt}_{func}"

# Assembling functions for I-type (handling immediate values and branch offsets)
def assemble_i_type(opcode, operands, label_map=None, current_address=None):
    if '(' in operands[1] and ')' in operands[1]:
        offset, base = operands[1].replace(')', '').split('(')
        immediate = format(parse_immediate(offset) & 0xFFFF, '016b')
        rt = registers[operands[0]]
        rs = registers[base]
    elif opcode in ['beq', 'bne'] and label_map and current_address is not None:
        rs = registers[operands[0]]
        rt = registers[operands[1]]
        label_address = label_map[operands[2]]
        offset = label_address - current_address
        immediate = format(offset & 0xFFFF, '016b')
    else:
        rt = registers[operands[0]]
        rs = registers[operands[1]]
        immediate = format(parse_immediate(operands[2]) & 0xFFFF, '016b')
    return f"{opcodes[opcode]}_{rs}_{rt}_{immediate}"

# Assembling functions for J-type (handling jump addresses)
def assemble_j_type(opcode, operands, label_map=None):
    if label_map:
        address = label_map[operands[0]]
        address = format(address, '026b')
    else:
        address = format(int(operands[0]), '026b')
    return f"{opcodes[opcode]}_{address}"

# Main function for assembling instructions
def assemble_instruction(opcode, operands, label_map=None, current_address=None):
    if opcode == 'nop':
        return f'00000000000000000000000000000000'
    elif opcode == "sgt":
        operands = [operands[0], operands[2], operands[1]]
        opcode = "slt"
        return assemble_r_type(opcode, operands)
    elif opcode == "move":
        operands = [operands[0], operands[1], '$0']
        opcode = "add"
        return assemble_r_type(opcode, operands)
    elif opcode == "li":
        operands = [operands[0], '$0', operands[1]]
        opcode = "addi"
        return assemble_i_type(opcode, operands)
    temp_reg = "$25"
    if opcode == "blt":
        slt_instruction = assemble_r_type("slt", [temp_reg, operands[0], operands[1]])
        bne_instruction = assemble_i_type("bne", [temp_reg, "$0", operands[2]], label_map, current_address)
        return f"{slt_instruction}\n{bne_instruction}"
    elif opcode == "bgt":
        slt_instruction = assemble_r_type("slt", [temp_reg, operands[1], operands[0]])
        bne_instruction = assemble_i_type("bne", [temp_reg, "$0", operands[2]], label_map, current_address)
        return f"{slt_instruction}\n{bne_instruction}"
    elif opcode == "ble":
        slt_instruction = assemble_r_type("slt", [temp_reg, operands[1], operands[0]])
        beq_instruction = assemble_i_type("beq", [temp_reg, "$0", operands[2]], label_map, current_address)
        return f"{slt_instruction}\n{beq_instruction}"
    elif opcode == "bge":
        slt_instruction = assemble_r_type("slt", [temp_reg, operands[0], operands[1]])
        beq_instruction = assemble_i_type("beq", [temp_reg, "$0", operands[2]], label_map, current_address)
        return f"{slt_instruction}\n{beq_instruction}"
    if opcode in func_codes:
        return assemble_r_type(opcode, operands)
    elif opcode in ["lw", "sw", "addi", "addiu", "andi", "ori", "xori", "slti", "sltiu", "beq", "bne"]:
        return assemble_i_type(opcode, operands, label_map, current_address)
    elif opcode in ["j", "jal"]:
        return assemble_j_type(opcode, operands, label_map)

# Main function for processing the assembly code
def main():
    with open("input.txt", "r") as f:
        lines = f.readlines()

    label_map = {}
    pc = 0

    # First pass: Collect labels and their addresses (line numbers)
    for line in lines:
        line = line.strip()
        part = line.replace(',', ' ').split()
         # Skip processing if the line doesn't split into parts (e.g., blank or invalid lines)
        if part:
            opcode = part[0].lower()
        else :
            continue
    
        if line.endswith(":"):
            label_map[line[:-1]] = pc  # Remove ':' and store label
        elif line and not line.startswith('#'):  # Only increment PC if it's a non-empty instruction and doesnt start with #(comment)
            if opcode in ["blt" ,"bgt" ,"ble" ,"bge"] :
                pc +=2
            else :
                pc += 1

    # Second pass: Process instructions
    with open("output.txt", "w") as f:
        pc = 0
        for line in lines:
            line = line.strip()
            if line.endswith(":") or line.startswith('#'):  # Skip label lines in the second pass
                continue
            if line:  # Process only non-empty lines (instructions)
                # Ignore comments (anything after a '#')
                line = line.split('#')[0].strip()  # Remove everything after '#' and strip extra spaces
                if line:  # Skip empty lines after removing comments
                    opcode, operands = parse_instruction(line)
                    if opcode in ["blt" ,"bgt" ,"ble" ,"bge"] :
                        pc +=1
                    binary_instructions = assemble_instruction(opcode, operands, label_map, pc)
                    for binary_instruction in binary_instructions.splitlines():
                        hex_instruction = f"{int(binary_instruction.replace('_', ''), 2):08X}"
                        f.write(f"{line} --> [ binary: {binary_instruction}, hex: {hex_instruction} ]\n")
                    pc += 1


main()
