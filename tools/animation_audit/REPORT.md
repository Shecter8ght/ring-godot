# RING animation audit

TOTAL FBX: 275
EXACT DUPLICATES: 0 groups / 0 excess copies
UNIQUE FBX: 275
ANIMATION PACKS: 24

COVERAGE: 48/96 target states; 121 shortlist entries.
Это предварительный отбор по именам. Визуальное качество и финальный набор пока не определены. Исходные FBX не изменялись.

## Animation pack analysis

| Pack | FBX | Unique | Target states | Pistol | Rifle | 8-way | Crouch | Prone | Reload | Death |
|---|---:|---:|---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| Pro Rifle Pack | 50 | 50 | 22 | NO | YES | YES | YES | NO | NO | YES |
| Rifle 8-Way Locomotion Pack | 50 | 50 | 22 | NO | YES | YES | YES | NO | NO | YES |
| Crouch weapons | 27 | 27 | 4 | NO | YES | NO | YES | YES | NO | YES |
| Pistol_Handgun Locomotion Pack | 20 | 20 | 7 | YES | NO | NO | YES | NO | NO | NO |
| Rifle | 19 | 19 | 8 | NO | YES | NO | YES | YES | NO | YES |
| Movements | 17 | 17 | 9 | NO | NO | NO | YES | NO | NO | NO |
| Basic Shooter Pack | 16 | 16 | 8 | NO | YES | NO | NO | NO | YES | NO |
| death | 15 | 15 | 4 | NO | YES | NO | YES | YES | NO | YES |
| Shooter Pack | 15 | 15 | 4 | NO | YES | NO | NO | NO | NO | YES |
| pistol | 13 | 13 | 9 | YES | NO | NO | YES | NO | NO | NO |
| Run rifles | 7 | 7 | 2 | NO | YES | NO | NO | NO | NO | YES |
| prone | 5 | 5 | 2 | NO | NO | NO | NO | YES | NO | NO |
| Gunplay | 4 | 4 | 0 | NO | NO | NO | NO | NO | NO | NO |
| jump away | 3 | 3 | 1 | NO | YES | NO | NO | NO | NO | NO |
| reload rifle | 3 | 3 | 1 | NO | YES | NO | NO | YES | YES | NO |
| hit | 2 | 2 | 2 | NO | NO | NO | NO | NO | NO | NO |
| Run Pistols | 2 | 2 | 2 | YES | NO | NO | NO | NO | NO | NO |
| Drawing pistol | 1 | 1 | 0 | YES | NO | NO | NO | NO | NO | NO |
| grenade | 1 | 1 | 1 | NO | NO | NO | NO | NO | NO | NO |
| jump low with pistol | 1 | 1 | 1 | YES | NO | NO | NO | NO | NO | NO |
| pick up | 1 | 1 | 1 | NO | NO | NO | NO | NO | NO | NO |
| Rifle idle | 1 | 1 | 1 | NO | YES | NO | NO | NO | NO | NO |
| run grenades | 1 | 1 | 1 | NO | NO | NO | NO | NO | NO | NO |
| shooting rifle | 1 | 1 | 1 | NO | YES | NO | NO | NO | NO | NO |

`Target states` — покрытие по названиям файлов и папок, а не подтверждение совместимости.
Самые полные по этому признаку — Pro Rifle Pack и Rifle 8-Way Locomotion Pack (по 22 состояния после исключения переходных клипов). Названия их файлов почти совпадают, но SHA-256 различается: автоматически считать их дублями нельзя.

## Animation coverage

| State | Found | Candidates |
|---|:---:|---:|
| Unarmed / Idle | YES | 1 |
| Unarmed / Walk Forward | YES | 1 |
| Unarmed / Walk Backward | YES | 1 |
| Unarmed / Walk Left | YES | 1 |
| Unarmed / Walk Right | YES | 1 |
| Unarmed / Run Forward | YES | 2 |
| Unarmed / Run Backward | YES | 1 |
| Unarmed / Run Left | NO | 0 |
| Unarmed / Run Right | NO | 0 |
| Unarmed / Crouch Idle | YES | 1 |
| Unarmed / Crouch Walk Forward | NO | 0 |
| Unarmed / Crouch Walk Backward | NO | 0 |
| Unarmed / Crouch Walk Left | NO | 0 |
| Unarmed / Crouch Walk Right | NO | 0 |
| Pistol / Idle | YES | 2 |
| Pistol / Aim Idle | NO | 0 |
| Pistol / Walk HIP Forward | YES | 2 |
| Pistol / Walk HIP Backward | YES | 2 |
| Pistol / Walk HIP Left | NO | 0 |
| Pistol / Walk HIP Right | YES | 1 |
| Pistol / Walk ADS Forward | NO | 0 |
| Pistol / Walk ADS Backward | NO | 0 |
| Pistol / Walk ADS Left | NO | 0 |
| Pistol / Walk ADS Right | NO | 0 |
| Pistol / Run Forward | YES | 3 |
| Pistol / Run Backward | YES | 3 |
| Pistol / Run Left | NO | 0 |
| Pistol / Run Right | NO | 0 |
| Pistol / Crouch Idle | YES | 2 |
| Pistol / Crouch Walk Forward | NO | 0 |
| Pistol / Crouch Walk Backward | NO | 0 |
| Pistol / Crouch Walk Left | NO | 0 |
| Pistol / Crouch Walk Right | NO | 0 |
| Pistol / Fire | NO | 0 |
| Pistol / Aim Fire | NO | 0 |
| Pistol / Reload | NO | 0 |
| Pistol / Empty Reload | NO | 0 |
| Pistol / Draw | NO | 0 |
| Pistol / Holster | NO | 0 |
| Pistol / Jump | YES | 3 |
| Pistol / Land | NO | 0 |
| Rifle / SMG / Idle | YES | 3 |
| Rifle / SMG / Aim Idle | YES | 4 |
| Rifle / SMG / Walk HIP Forward | YES | 2 |
| Rifle / SMG / Walk HIP Backward | YES | 2 |
| Rifle / SMG / Walk HIP Left | YES | 2 |
| Rifle / SMG / Walk HIP Right | YES | 2 |
| Rifle / SMG / Walk ADS Forward | NO | 0 |
| Rifle / SMG / Walk ADS Backward | NO | 0 |
| Rifle / SMG / Walk ADS Left | NO | 0 |
| Rifle / SMG / Walk ADS Right | NO | 0 |
| Rifle / SMG / Run Forward | YES | 5 |
| Rifle / SMG / Run Backward | YES | 2 |
| Rifle / SMG / Run Left | YES | 2 |
| Rifle / SMG / Run Right | YES | 2 |
| Rifle / SMG / Sprint | YES | 2 |
| Rifle / SMG / Crouch Idle | YES | 2 |
| Rifle / SMG / Crouch Walk Forward | YES | 3 |
| Rifle / SMG / Crouch Walk Backward | YES | 2 |
| Rifle / SMG / Crouch Walk Left | YES | 2 |
| Rifle / SMG / Crouch Walk Right | YES | 2 |
| Rifle / SMG / Prone Idle | NO | 0 |
| Rifle / SMG / Prone Move Forward | NO | 0 |
| Rifle / SMG / Prone Move Backward | NO | 0 |
| Rifle / SMG / Prone Move Left | NO | 0 |
| Rifle / SMG / Prone Move Right | NO | 0 |
| Rifle / SMG / Fire | YES | 3 |
| Rifle / SMG / Aim Fire | NO | 0 |
| Rifle / SMG / Reload | YES | 2 |
| Rifle / SMG / Empty Reload | NO | 0 |
| Rifle / SMG / Draw | YES | 1 |
| Rifle / SMG / Holster | YES | 1 |
| Rifle / SMG / Jump | YES | 5 |
| Rifle / SMG / Land | YES | 2 |
| Grenade / Idle / Hold | NO | 0 |
| Grenade / Throw | YES | 4 |
| Grenade / Movement | NO | 0 |
| Grenade / Run | NO | 0 |
| Hit / Forward | YES | 5 |
| Hit / Backward | NO | 0 |
| Hit / Left | NO | 0 |
| Hit / Right | NO | 0 |
| Hit / Secondary | YES | 5 |
| Death / Forward | YES | 5 |
| Death / Backward | YES | 5 |
| Death / Left | NO | 0 |
| Death / Right | YES | 4 |
| Death / Secondary | YES | 5 |
| Interaction / Pickup | YES | 1 |
| Interaction / Generic | NO | 0 |
| Optional / Turn in Place | YES | 5 |
| Optional / Dodge / Evade | YES | 2 |
| Optional / Melee | NO | 0 |
| Optional / Weapon Inspect | NO | 0 |
| Optional / Low Ready | NO | 0 |
| Optional / High Ready | NO | 0 |

## Exact duplicate groups

No byte-identical files found.

Potential semantic groups: 79. See `semantic_groups.json`; names alone do not establish animation equivalence.

## Technical integration notes

- The source files have not been converted, moved, or modified.
- Current audit uses filenames and folders for state preselection. Visual judgments require the shortlist viewer.
- All 275 source headers identify binary FBX version 7700.
- Target character: `D:/ПРОГРАММЫ/Blender 5/Projects/Persona.blend` (read-only inspection). It has 13 mesh objects and an armature of 52 bones, with root `mixamorig:Hips`.
- Blender probe of one FBX from each of 24 packs found 0 meshes, 65 bones and the same root in all 24. All 52 character bone names occur in each sampled FBX. See `rig_probe.json` for individual names and scales.
- The 13 additional animation bones and bind pose must be checked before retargeting. Identical names alone do not prove identical transforms or animation compatibility.
- Root motion, orientation, unit scale in motion, and rest/bind pose remain unverified. Compare poses and root trajectories after final visual selection.
- A state marked FOUND means a plausible name match. ADS walk and empty reload remain missing unless their names explicitly identify these actions.
- `Persona.fbx` in a pack is a character file; it is inventory-only and not a locomotion candidate.
