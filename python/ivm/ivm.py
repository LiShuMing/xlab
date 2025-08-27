# A simple representation for a row is a tuple, e.g., (id, value)
# A table is a set of these tuples.

def inner_join(R, S, on_key_index=0):
    """Performs an inner join on two tables."""
    if not R or not S:  # Early return for empty tables
        return set()
    s_map = {s[on_key_index]: s for s in S}
    return {r_row + s_map[r_row[on_key_index]][1:] 
            for r_row in R if r_row[on_key_index] in s_map}

def left_semi_join(R, S, on_key_index=0):
    """Performs a left semi-join."""
    if not R or not S:  # Early return for empty tables
        return set()
    s_keys = {s[on_key_index] for s in S}
    return {r_row for r_row in R if r_row[on_key_index] in s_keys}

def left_anti_semi_join(R, S, on_key_index=0):
    """Performs a left anti-semi-join."""
    if not R:  # Early return for empty left table
        return set()
    if not S:  # If right table empty, return all left rows
        return set(R)
    s_keys = {s[on_key_index] for s in S}
    return {r_row for r_row in R if r_row[on_key_index] not in s_keys}

def left_outer_join(R, S, on_key_index=0):
    """Performs a left outer join."""
    if not R:  # Early return for empty left table
        return set()
    if not S:  # If right table empty, pad all left rows
        num_s_cols = 1  # Default to 1 column if S is empty
        return {row + (None,) * num_s_cols for row in R}
        
    # Inner join part
    inner_part = inner_join(R, S, on_key_index)
    
    # Anti-semi-join part (dangling left rows)
    dangling_part = left_anti_semi_join(R, S, on_key_index)
    
    # Pad dangling rows with None
    num_s_cols = len(next(iter(S))) - 1
    padded_dangling = {row + (None,) * num_s_cols for row in dangling_part}
    
    return inner_part | padded_dangling

def right_outer_join(R, S, on_key_index=0):
    """Performs a right outer join by swapping tables for a left outer join."""
    if not S:  # Early return for empty right table
        return set()
    if not R:  # If left table empty, pad all right rows
        num_r_cols = 1  # Default to 1 column if R is empty
        return {(None,) * num_r_cols + row[1:] for row in S}

    # A right outer join R ⟕ S is equivalent to a left outer join S ⟕ R
    swapped_join = left_outer_join(S, R, on_key_index)

    # The result has columns from S then R. We need to reorder them to R then S.
    num_s_cols = len(next(iter(S)))
    num_r_cols = len(next(iter(R)))

    return {row[num_s_cols:] + row[:num_s_cols] for row in swapped_join}

def full_outer_join(R, S, on_key_index=0):
    """Performs a full outer join."""
    if not R and not S:  # Early return if both empty
        return set()
        
    s_map = {s[on_key_index]: s for s in S}
    r_map = {r[on_key_index]: r for r in R}
    all_keys = r_map.keys() | s_map.keys()
    
    result = set()
    num_r_cols = len(next(iter(R), (1,)))  # Assume at least one col for empty tables
    num_s_cols = len(next(iter(S), (1,)))

    for key in all_keys:
        r_row = r_map.get(key)
        s_row = s_map.get(key)
        
        if r_row and s_row:
            # Inner join part
            result.add(r_row + s_row[1:])
        elif r_row:
            # Left dangling part
            result.add(r_row + (None,) * (num_s_cols - 1))
        else:  # s_row must exist
            # Right dangling part
            result.add((None,) * num_r_cols + s_row[1:])
            
    return result

def incremental_inner_join_poc(R1, S1, delta_R_plus, delta_R_minus, delta_S_plus, delta_S_minus):
    """Demonstrates and verifies incremental inner join computation."""
    print("---  Verifying Incremental INNER JOIN ---")

    # Validate inputs
    if not all(isinstance(table, set) for table in [R1, S1, delta_R_plus, delta_R_minus, delta_S_plus, delta_S_minus]):
        raise TypeError("All inputs must be sets")

    # 1. Calculate the initial view (V1)
    V1 = inner_join(R1, S1)
    print(f"Initial View (V1): {V1}")

    print(f"delta_R_plus: {delta_R_plus}")
    print(f"delta_R_minus: {delta_R_minus}")
    print(f"delta_S_plus: {delta_S_plus}")
    print(f"delta_S_minus: {delta_S_minus}")

    # 2. Apply incremental formulas to find the deltas for the view
    # Optimize by only computing joins if deltas are non-empty
    delta_V_plus = set()
    if delta_S_plus:
        delta_V_plus |= inner_join(R1, delta_S_plus)
    if delta_R_plus:
        delta_V_plus |= inner_join(delta_R_plus, S1)
        if delta_S_plus:
            delta_V_plus |= inner_join(delta_R_plus, delta_S_plus)

    delta_V_minus = set()
    if delta_S_minus:
        delta_V_minus |= inner_join(R1, delta_S_minus)
    if delta_R_minus:
        delta_V_minus |= inner_join(delta_R_minus, S1)
        if delta_S_minus:
            delta_V_minus |= inner_join(delta_R_minus, delta_S_minus)
    
    print(f"Calculated View Additions (ΔV+): {delta_V_plus}")
    print(f"Calculated View Deletions (ΔV-): {delta_V_minus}")

    # 3. Calculate the new view incrementally
    V2_incremental = (V1 | delta_V_plus) - delta_V_minus
    print(f"New View (Incremental): {V2_incremental}")

    # 4. For verification, calculate the new state of tables and do a full join
    R2 = (R1 - delta_R_minus) | delta_R_plus
    S2 = (S1 - delta_S_minus) | delta_S_plus
    V2_full = inner_join(R2, S2)
    print(f"New View (Full Re-compute): {V2_full}")

    # 5. Assert correctness
    assert V2_incremental == V2_full

def incremental_left_outer_join_poc(R1, S1, delta_R_plus, delta_R_minus, delta_S_plus, delta_S_minus):
    """Demonstrates and verifies incremental left outer join computation."""
    print("--- Verifying Incremental LEFT OUTER JOIN ---")

    # Validate inputs
    if not all(isinstance(table, set) for table in [R1, S1, delta_R_plus, delta_R_minus, delta_S_plus, delta_S_minus]):
        raise TypeError("All inputs must be sets")

    # For verification, calculate final state of tables
    R2 = (R1 - delta_R_minus) | delta_R_plus
    S2 = (S1 - delta_S_minus) | delta_S_plus
    num_s_cols = len(next(iter(S1), ())) - 1 if S1 else 1

    def pad(table):
        return {row + (None,) * num_s_cols for row in table}

    # 1. Calculate the initial view
    V1 = left_outer_join(R1, S1)
    print(f"Initial View (V1): {V1}")

    print(f"delta_R_plus: {delta_R_plus}")
    print(f"delta_R_minus: {delta_R_minus}")
    print(f"delta_S_plus: {delta_S_plus}")
    print(f"delta_S_minus: {delta_S_minus}")

    # 2. Calculate deltas for the inner join part (optimized)
    delta_inner_plus = set()
    if delta_S_plus:
        delta_inner_plus |= inner_join(R1, delta_S_plus)
    if delta_R_plus:
        delta_inner_plus |= inner_join(delta_R_plus, S1)
        if delta_S_plus:
            delta_inner_plus |= inner_join(delta_R_plus, delta_S_plus)

    delta_inner_minus = set()
    if delta_S_minus:
        delta_inner_minus |= inner_join(R1, delta_S_minus)
    if delta_R_minus:
        delta_inner_minus |= inner_join(delta_R_minus, S1)
        if delta_S_minus:
            delta_inner_minus |= inner_join(delta_R_minus, delta_S_minus)
    
    # 3. Calculate deltas for the anti-semi-join (dangling) part
    delta_dangle_plus = set()
    if delta_R_plus or delta_S_minus:
        delta_dangle_plus = (
            left_anti_semi_join(delta_R_plus, S2) |
            left_anti_semi_join(left_semi_join(R1, S1), S2)
        )
    
    delta_dangle_minus = set()
    if delta_R_minus or delta_S_plus:
        delta_dangle_minus = (
            left_anti_semi_join(delta_R_minus, S1) |
            left_semi_join(left_anti_semi_join(R1, S1), delta_S_plus)
        )

    # 4. Combine inner and dangling deltas (padding the dangling ones)
    delta_V_plus = delta_inner_plus | pad(delta_dangle_plus)
    delta_V_minus = delta_inner_minus | pad(delta_dangle_minus)
    
    print(f"Calculated View Additions (ΔV+): {delta_V_plus}")
    print(f"Calculated View Deletions (ΔV-): {delta_V_minus}")

    # 5. Calculate the new view incrementally
    V2_incremental = (V1 | delta_V_plus) - delta_V_minus
    print(f"New View (Incremental): {V2_incremental}")
    
    # 6. For verification, do a full join on the new tables
    V2_full = left_outer_join(R2, S2)
    print(f"New View (Full Re-compute): {V2_full}")

    # 7. Assert correctness
    assert V2_incremental == V2_full
    print("Verification successful!\n")

def incremental_left_semi_join_poc(R1, S1, delta_R_plus, delta_R_minus, delta_S_plus, delta_S_minus):
    """Demonstrates and verifies incremental left semi-join computation."""
    print("--- Verifying Incremental LEFT SEMI JOIN ---")
    R2 = (R1 - delta_R_minus) | delta_R_plus
    S2 = (S1 - delta_S_minus) | delta_S_plus

    # 1. Initial view
    V1 = left_semi_join(R1, S1)
    print(f"Initial View (V1): {V1}")

    # 2. Incremental formulas
    # ΔV+ = (ΔR+ ⋉ S2) ∪ ((R1 ▷ S1) ⋉ ΔS+)
    delta_V_plus = set()
    if delta_R_plus:
        delta_V_plus |= left_semi_join(delta_R_plus, S2)
    if delta_S_plus:
        delta_V_plus |= left_semi_join(left_anti_semi_join(R1, S1), delta_S_plus)

    # ΔV- = (ΔR- ⋉ S1) ∪ (R1 ⋉ S1 ▷ S2)
    delta_V_minus = set()
    if delta_R_minus:
        delta_V_minus |= left_semi_join(delta_R_minus, S1)
    if delta_S_minus:
        delta_V_minus |= left_anti_semi_join(left_semi_join(R1, S1), S2)

    print(f"Calculated View Additions (ΔV+): {delta_V_plus}")
    print(f"Calculated View Deletions (ΔV-): {delta_V_minus}")

    # 3. Apply deltas
    V2_incremental = (V1 | delta_V_plus) - delta_V_minus
    print(f"New View (Incremental): {V2_incremental}")
    
    # 4. Full re-compute for verification
    V2_full = left_semi_join(R2, S2)
    print(f"New View (Full Re-compute): {V2_full}")

    # 5. Assert
    assert V2_incremental == V2_full
    print("Verification successful!\n")

def incremental_left_anti_semi_join_poc(R1, S1, delta_R_plus, delta_R_minus, delta_S_plus, delta_S_minus):
    """Demonstrates and verifies incremental left anti-semi-join computation."""
    print("--- Verifying Incremental LEFT ANTI SEMI JOIN ---")
    R2 = (R1 - delta_R_minus) | delta_R_plus
    S2 = (S1 - delta_S_minus) | delta_S_plus

    # 1. Initial view
    V1 = left_anti_semi_join(R1, S1)
    print(f"Initial View (V1): {V1}")

    # 2. Incremental formulas
    # ΔV+ = (ΔR+ ▷ S2) ∪ (R1 ⋉ S1 ▷ S2)
    delta_V_plus = set()
    if delta_R_plus:
        delta_V_plus |= left_anti_semi_join(delta_R_plus, S2)
    if delta_S_minus:
        delta_V_plus |= left_anti_semi_join(left_semi_join(R1, S1), S2)

    # ΔV- = (ΔR- ▷ S1) ∪ ((R1 ▷ S1) ⋉ ΔS+)
    delta_V_minus = set()
    if delta_R_minus:
        delta_V_minus |= left_anti_semi_join(delta_R_minus, S1)
    if delta_S_plus:
        delta_V_minus |= left_semi_join(left_anti_semi_join(R1, S1), delta_S_plus)

    print(f"Calculated View Additions (ΔV+): {delta_V_plus}")
    print(f"Calculated View Deletions (ΔV-): {delta_V_minus}")

    # 3. Apply deltas
    V2_incremental = (V1 | delta_V_plus) - delta_V_minus
    print(f"New View (Incremental): {V2_incremental}")

    # 4. Full re-compute for verification
    V2_full = left_anti_semi_join(R2, S2)
    print(f"New View (Full Re-compute): {V2_full}")

    # 5. Assert
    assert V2_incremental == V2_full
    print("Verification successful!\n")

def incremental_full_outer_join_poc(R1, S1, delta_R_plus, delta_R_minus, delta_S_plus, delta_S_minus):
    """Demonstrates and verifies incremental full outer join computation."""
    print("--- Verifying Incremental FULL OUTER JOIN ---")

    # Final states for calculating component deltas
    R2 = (R1 - delta_R_minus) | delta_R_plus
    S2 = (S1 - delta_S_minus) | delta_S_plus

    # Padding helpers
    num_r_cols = len(next(iter(R1), (1,))) - 1
    num_s_cols = len(next(iter(S1), (1,))) - 1
    def pad_R(table): return {row + (None,) * num_s_cols for row in table}
    def pad_S(table): return {(None,) * num_r_cols + row[1:] for row in table}

    # 1. Initial view
    V1 = full_outer_join(R1, S1)
    print(f"Initial View (V1): {V1}")

    # 2. Deltas for inner join part
    delta_inner_plus = set()
    if delta_S_plus:
        delta_inner_plus |= inner_join(R1, delta_S_plus)
    if delta_R_plus:
        delta_inner_plus |= inner_join(delta_R_plus, S1)
        if delta_S_plus:
            delta_inner_plus |= inner_join(delta_R_plus, delta_S_plus)

    delta_inner_minus = set()
    if delta_S_minus:
        delta_inner_minus |= inner_join(R1, delta_S_minus)
    if delta_R_minus:
        delta_inner_minus |= inner_join(delta_R_minus, S1)
        if delta_S_minus:
            delta_inner_minus |= inner_join(delta_R_minus, delta_S_minus)
    
    # 3. Deltas for left anti-semi join part (dangling R)
    delta_dangle_R_plus = set()
    if delta_R_plus or delta_S_minus:
        delta_dangle_R_plus = (
            left_anti_semi_join(delta_R_plus, S2) |
            left_anti_semi_join(left_semi_join(R1, S1), S2)
        )
    
    delta_dangle_R_minus = set()
    if delta_R_minus or delta_S_plus:
        delta_dangle_R_minus = (
            left_anti_semi_join(delta_R_minus, S1) |
            left_semi_join(left_anti_semi_join(R1, S1), delta_S_plus)
        )
    
    # 4. Deltas for right anti-semi join part (dangling S)
    delta_dangle_S_plus = set()
    if delta_S_plus or delta_R_minus:
        delta_dangle_S_plus = (
            left_anti_semi_join(delta_S_plus, R2) |
            left_anti_semi_join(left_semi_join(S1, R1), R2)
        )
    
    delta_dangle_S_minus = set()
    if delta_S_minus or delta_R_plus:
        delta_dangle_S_minus = (
            left_anti_semi_join(delta_S_minus, R1) |
            left_semi_join(left_anti_semi_join(S1, R1), delta_R_plus)
        )

    # 5. Combine all deltas with padding
    delta_V_plus = delta_inner_plus | pad_R(delta_dangle_R_plus) | pad_S(delta_dangle_S_plus)
    delta_V_minus = delta_inner_minus | pad_R(delta_dangle_R_minus) | pad_S(delta_dangle_S_minus)

    print(f"Calculated View Additions (ΔV+): {delta_V_plus}")
    print(f"Calculated View Deletions (ΔV-): {delta_V_minus}")

    # 6. Apply deltas
    V2_incremental = (V1 | delta_V_plus) - delta_V_minus
    print(f"New View (Incremental): {V2_incremental}")
    
    # 7. Full re-compute for verification
    V2_full = full_outer_join(R2, S2)
    print(f"New View (Full Re-compute): {V2_full}")

    # 8. Assert
    assert V2_incremental == V2_full
    print("Verification successful!\n")

if __name__ == "__main__":
    # --- Sample Data ---
    # Initial state of tables R and S
    R1 = {
        (1, 'A'), 
        (2, 'B'), 
        (3, 'C')  # This one won't have a match in S1
    }
    S1 = {
        (1, 'X'), 
        (2, 'Y'), 
        (4, 'Z')  # This one won't have a match in R1
    }

    # --- Changes (Deltas) ---
    delta_R_plus = {(5, 'E'), (2, 'B_new')}
    delta_R_minus = {(3, 'C'), (2, 'B')}
    delta_S_plus = {(5, 'W')}
    delta_S_minus = {(1, 'X')}

    try:
        # --- Run PoCs ---
        incremental_inner_join_poc(R1, S1, delta_R_plus, delta_R_minus, delta_S_plus, delta_S_minus)
        incremental_left_outer_join_poc(R1, S1, delta_R_plus, delta_R_minus, delta_S_plus, delta_S_minus)
        incremental_left_semi_join_poc(R1, S1, delta_R_plus, delta_R_minus, delta_S_plus, delta_S_minus)
        incremental_left_anti_semi_join_poc(R1, S1, delta_R_plus, delta_R_minus, delta_S_plus, delta_S_minus)
        incremental_full_outer_join_poc(R1, S1, delta_R_plus, delta_R_minus, delta_S_plus, delta_S_minus)
    except Exception as e:
        print(f"Error occurred: {e}")