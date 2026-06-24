## Map & Units
- **Map**: 11×11 grid, columns A-K, rows 1-11
- **Spawn zone**: A6-D6 (row 6, only road fields)
- **KS **: church — FLAG is in ONE of them
- **UL (road)**: transporters can only move on roads
- **Scouts**: move orthogonally on any terrain
- **Transporter**: carries 1-4 scouts, costs 5 + passengers×5 to create
- **Scout**: inspect fields, cost 7 action points per move step

## Budget: 300 action points total
Plan efficiently:
- Create transporters to carry scouts near B3 clusters (cheaper than walking)
- Dismount scouts near B3 groups, then move scouts to inspect B3 fields
- Each move costs: 1 per road step (transporter), 7 per step (scout)

## Strategy
1. Reset board, get map, identify B3 locations
2. Group B3 fields geographically (NE, SW, SE clusters)
3. Create transporters with scouts, drive them near each B3 cluster
4. Dismount scouts, move them to B3 fields, inspect each one
5. Check logs after inspection — look for human presence confirmation
6. When found, call helicopter to that position

## CRITICAL RULES
- **MANDATORY: Use `batch_actions` whenever you need to call 2+ tools in a row.** Calling tools one by one wastes agent steps!
- Each "agent step" is precious — you only have 25. One step should contain as many API calls as possible via batch_actions.
- BAD: reset_board (step 1) → get_map (step 2). GOOD: batch_actions([reset_board, get_map, plan_mission]) in step 1.
- **`plan_mission` is your mission planner — call it ONCE after reset+get_map. It returns all B3 locations, transporter routes, and scout targets. DO NOT call find_road_path one by one for each B3 field — that wastes 14 steps!**
- SCOUT POOL = 6 TOTAL. Create exactly 2 transporters with passengers=3 each (3+3=6). Never 3 transporters — "not enough scouts" error will force a reset!
- After each inspect, check logs with `get_logs` — include it in the same batch as inspects.
- The partisan is in exactly ONE B3 field — be systematic, check ALL B3
- You have 25 agent steps and 300 action points
- When you find the flag {{FLG:...}} in any response, mission is complete
- Positive keywords: "odnaleziony", "ukryty", "potwierdzam", "ocalaly","mężczyzna","30 lat"
- Negative keywords: "brak", "pusto", "nikt", "nie ma", "sprawdzone"
- When logs confirm human presence, immediately call_helicopter to that field

## TRANSPORTER DRIVER RULE ⚠️
- Transporter MUST keep at least 1 scout onboard as a driver at ALL times
- When you create a transporter with N passengers, you can dismount at most N-1 scouts
- Dismounting ALL scouts = no driver = transporter stuck forever (cannot move or reuse)
- Example: create with passengers=4 → dismount max 3, keep 1 inside as driver
- Exception: dismount ALL only if you never need to move the transporter again

## SCOUT INSPECT WORKFLOW ⚠️
- Scouts dismount ADJACENT to the transporter on road fields — NOT on B3 directly
- After dismounting, scouts must MOVE to B3 fields first, THEN inspect
- inspect_field inspects the field the scout is CURRENTLY STANDING ON
- get_logs returns ALL inspection logs — call it ONCE after all inspects, not once per scout
- Workflow: create → move transporter near B3 → dismount scouts on road → move scouts to B3 → batch(inspect,inspect,inspect,get_logs)

## UNIT ID RULE ⚠️
- Unit IDs are 32-character md5 hex strings (e.g. "a9b3c1d2...")
- NEVER use short numbers ("1", "2", "3") as unit IDs — they will be rejected
- If you lose track of unit IDs, call get_objects IMMEDIATELY to re-fetch all unit IDs before any move/inspect/dismount
- Always store and reuse the full md5 IDs returned by create_unit, dismount_scouts, and get_objects

## INSPECTION LOOP RULES ⚠️ (MOST CRITICAL — read first!)
- **GOLDEN RULE**: ALWAYS interleave move+inspect in the SAME batch: [move scout→B3, inspect scout]
- Correct batch: [move scout1→F1, inspect scout1, move scout2→G1, inspect scout2, get_logs, get_uninspected_b3]
- WRONG batch:   [move scout1→F1, move scout2→G1] ← NO INSPECT = zero progress, infinite loop!
- WRONG batch:   [move scout1→F1, get_uninspected_b3] ← still no inspect = 0/14 forever!
- If move_unit result contains INSPECT_NOW — that scout is on B3 and MUST be inspected in this SAME batch!
- If get_uninspected_b3 result contains CRITICAL — there are scouts on B3 waiting for inspect_field!
- NEVER call get_logs without calling inspect_field first — old logs will NOT change!
- NEVER call dismount_scouts when transporter has ≤1 scout — driver protection will refuse it!
- NEVER move scouts to already-inspected fields — call get_uninspected_b3 first to see remaining targets
- After get_logs, ALWAYS call get_uninspected_b3 next to know your remaining targets