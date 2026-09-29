# Synthetic demo: pairwise programs -> local abstraction -> reduced search

pair 0: ground truth (map (λObject. (recolor (translate $0 down) c2)) $0)
```
0000
0100
0000
0000
->
0000
0000
0200
0000
```
pair 1: ground truth (map (λObject. (recolor (translate $0 up) c2)) $0)
```
0000
0000
0030
0000
->
0000
0020
0000
0000
```
pair 2: ground truth (map (λObject. (recolor (translate $0 left) c2)) $0)
```
0400
0000
0000
0000
->
2000
0000
0000
0000
```

## Local wake (each pair searched alone)
- pair 0: (map (λObject. (translate (recolor $0 c2) down)) $0)  (expanded_states=62271, first_solution_states=62271)
- pair 1: (map (λObject. (translate (recolor $0 c2) up)) $0)  (expanded_states=62338, first_solution_states=62338)
- pair 2: (map (λObject. (translate (recolor $0 c2) left)) $0)  (expanded_states=63839, first_solution_states=63839)

## Local sleep (compression)
- MDL 24 -> 18; pruned []
- accepted `#f0 = λx0:Vec2 x1:ObjectSet. (map (λObject. (translate (recolor $0 c2) $2)) $0)`  (13 candidates scored)
  - rewritten: ['(#f0 down $0)']
  - rewritten: ['(#f0 up $0)']
  - rewritten: ['(#f0 left $0)']

## Full-task search (all pairs), fixed DSL vs TSL_τ
- target program: (map (λObject. (recolor (translate $0 right) c2)) $0)
- fixed DSL : solved=True program=(map (λObject. (translate (recolor $0 c2) right)) $0) expanded_states=93456 first_solution_states=93456 seconds=1.74 L=8
- TSL_τ     : solved=True program=(#f0 right $0) expanded_states=148 first_solution_states=148 seconds=0.05 L=3 L(A_τ)=9
- expanded-state ratio (fixed / TSL): 631.46; first-solution ratio: 631.46; wake cost: 188448 states
- expanded TSL program: (map (λObject. (translate (recolor $0 c2) right)) $0)