
def is_special(hex_instr):
    """
    Determine if the instruction (given as an 8-digit hex string) is 'special'
    (i.e. must be in slot2). Special opcodes (first 6 bits) include:
      - j (opcode 2), jal (opcode 3)
      - beq (opcode 4), bne (opcode 5)
      - lw (opcode 35), sw (opcode 43)
    NOP (00000000) is not considered special.
    """
    if hex_instr == "00000000":
        return False
    instr_int = int(hex_instr, 16)
    opcode = (instr_int >> 26) & 0x3F
    return opcode in {2, 3, 4, 5, 35, 43}

def decode_mips(hex_instr):
    """
    Decode a 32-bit MIPS instruction (as an 8-digit hex string)
    into its read and write register sets.
    Returns a dictionary with:
      - type: "R", "I", "J", or "nop"
      - opcode: integer opcode value
      - reads: set of register numbers read
      - writes: set of register numbers written

    For simplicity:
      * R-type (opcode 0):
          - Shift instructions (sll, srl, sra: funct 0,2,3) read only rt.
          - jr (funct 8) reads only rs.
          - Otherwise, reads {rs, rt} and writes {rd}.
      * I-type:
          - Branches (opcode 4,5): read {rs, rt}, no write.
          - lw (35): read {rs}, write {rt}.
          - sw (43): read {rs, rt}, no write.
          - Otherwise (e.g. addi): read {rs}, write {rt}.
      * J-type:
          - j (opcode 2) reads nothing.
          - jal (opcode 3) writes to register 31.
      * NOP is treated as type "nop" with no register usage.
    """
    if hex_instr == "00000000":
        return {"type": "nop", "opcode": 0, "reads": set(), "writes": set()}
    instr = int(hex_instr, 16)
    opcode = (instr >> 26) & 0x3F
    if opcode == 0:  # R-type
        funct = instr & 0x3F
        rs = (instr >> 21) & 0x1F
        rt = (instr >> 16) & 0x1F
        rd = (instr >> 11) & 0x1F
        if funct in {0, 2, 3}:  # shift instructions
            return {"type": "R", "opcode": opcode, "funct": funct, "reads": {rt}, "writes": {rd}}
        elif funct == 8:  # jr
            return {"type": "R", "opcode": opcode, "funct": funct, "reads": {rs}, "writes": set()}
        else:
            return {"type": "R", "opcode": opcode, "funct": funct, "reads": {rs, rt}, "writes": {rd}}
    elif opcode in {2, 3}:  # J-type
        if opcode == 3:  # jal writes to $31
            return {"type": "J", "opcode": opcode, "reads": set(), "writes": {31}}
        else:
            return {"type": "J", "opcode": opcode, "reads": set(), "writes": set()}
    else:  # I-type
        rs = (instr >> 21) & 0x1F
        rt = (instr >> 16) & 0x1F
        if opcode in {4, 5}:  # branches: beq, bne
            return {"type": "I", "opcode": opcode, "reads": {rs, rt}, "writes": set()}
        elif opcode == 35:  # lw
            return {"type": "I", "opcode": opcode, "reads": {rs}, "writes": {rt}}
        elif opcode == 43:  # sw
            return {"type": "I", "opcode": opcode, "reads": {rs, rt}, "writes": set()}
        else:
            return {"type": "I", "opcode": opcode, "reads": {rs}, "writes": {rt}}

def can_schedule_in_slot1(candidate_hex, special_hex):
    """
    Check if a candidate non-special instruction can safely be scheduled
    in slot1 with the given special instruction in slot2.
    The candidate is safe if:
      - Its write set does not intersect the special's read set.
      - The special's write set does not intersect the candidate's read set.
    """
    cand = decode_mips(candidate_hex)
    spec = decode_mips(special_hex)
    if cand['writes'] & spec['reads']:
        return False
    if spec['writes'] & cand['reads']:
        return False
    return True

def safe_pair(hex1, hex2):
    """
    Check if two instructions (given by their hex strings) can be safely
    issued in the same packet (i.e. no data hazard between them).
    Returns True if safe, False otherwise.
    """
    inst1 = decode_mips(hex1)
    inst2 = decode_mips(hex2)
    if inst1['writes'] & inst2['reads']:
        return False
    if inst2['writes'] & inst1['reads']:
        return False
    return True

def read_instructions(file_path):
    """
    Read the assembler's output file and extract a list of instructions.
    Each line is expected to be in the format:
       binary: <binary_string>, hex: <hex_string>
    Returns a list of tuples: (full_line, hex_string)
    """
    instructions = []
    with open(file_path, 'r') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            if "hex:" in line:
                parts = line.split("hex:")
                # Extract only the actual hex digits.
                hex_code = parts[1].strip().split()[0]
                instructions.append((line, hex_code))
    return instructions

def schedule_instructions_enhanced(instructions):
    """
    Schedule instructions into dual-issue packets with enhanced filling.
    The algorithm works as follows:
      - For each unscheduled instruction:
          * If it is special (must be in slot2), scan ahead for an unscheduled,
            non-special candidate that is hazard-safe (using can_schedule_in_slot1).
            If found, schedule that candidate in slot1; otherwise, use a NOP.
          * If it is non-special, scan ahead for an unscheduled candidate that is
            safe to pair (using safe_pair). If found, schedule them in the same packet.
            If no safe candidate is available, pair with a NOP.
    The algorithm preserves program order and uses a 'used' flag array.
    """
    n = len(instructions)
    used = [False] * n
    packets = []
    nop_line = "binary: 00000000000000000000000000000000, hex: 00000000"
    i = 0
    while i < n:
        if used[i]:
            i += 1
            continue

        curr_line, curr_hex = instructions[i]
        if is_special(curr_hex):
            # For a special instruction, try to find a candidate for slot1.
            candidate_index = None
            for j in range(i + 1, n):
                if not used[j]:
                    cand_line, cand_hex = instructions[j]
                    if not is_special(cand_hex) and can_schedule_in_slot1(cand_hex, curr_hex):
                        candidate_index = j
                        break
            if candidate_index is not None:
                packets.append((instructions[candidate_index][0], curr_line))
                used[candidate_index] = True
                used[i] = True
            else:
                packets.append((nop_line, curr_line))
                used[i] = True
            i += 1
        else:
            # For a non-special instruction, try to find the next unscheduled instruction
            # that can be safely paired with it (using safe_pair).
            candidate_index = None
            for j in range(i + 1, n):
                if not used[j]:
                    cand_line, cand_hex = instructions[j]
                    if safe_pair(curr_hex, cand_hex):
                        candidate_index = j
                        break
            if candidate_index is not None:
                packets.append((curr_line, instructions[candidate_index][0]))
                used[i] = True
                used[candidate_index] = True
            else:
                packets.append((curr_line, nop_line))
                used[i] = True
            i += 1
    return packets

def main():
    input_file = "output.txt"                 # Input file from the assembler
    output_file = "scheduled_instructions.txt"  # File for the scheduled instructions

    # Read instructions from the assembler's output.
    instructions = read_instructions(input_file)
    if not instructions:
        print("No instructions found in", input_file)
        return

    # Schedule instructions into dual-issue packets with enhanced scheduling.
    packets = schedule_instructions_enhanced(instructions)

    # Write the scheduled packets to the separate file.
    with open(output_file, 'w') as f:
        for idx, (slot1, slot2) in enumerate(packets, start=1):
            f.write(f"Packet {idx}:\n")
            f.write(f"  Slot1: {slot1}\n")
            f.write(f"  Slot2: {slot2}\n\n")

    print(f"Scheduling complete. Scheduled instructions written to '{output_file}'.")

if __name__ == '__main__':
    main()
