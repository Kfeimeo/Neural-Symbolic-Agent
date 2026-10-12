"""Domain base types declared by the DSA."""
from ..ml.types import Type

OBJECT = Type("Object")
OBJECTS = Type("ObjectSet")
COLOR = Type("Color")
VEC2 = Type("Vec2")
SHAPE = Type("ShapeId")
TURN = Type("QuarterTurn")
AXIS = Type("Axis")
REGION = Type("Region")
COLORSET = Type("ColorSet")
GRID = Type("Grid")
POS = Type("Pos")
DIMS = Type("Dims")
PATCH = Type("Shape")  # colored, oriented local pixels; distinct from ShapeId
MASK = Type("LocalMask")
