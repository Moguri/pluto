import msgspec
import panda3d.core as p3d


class Vec2H(p3d.Vec2F):
    pass

class Vec3H(p3d.Vec3F):
    pass

class Vec4H(p3d.Vec4F):
    pass

VecTypes = (
    p3d.Vec2F
    | p3d.Vec3F
    | p3d.Vec4F
    | p3d.Vec2D
    | p3d.Vec3D
    | p3d.Vec4D
)


class NetworkMessage(msgspec.Struct, array_like=True, kw_only=True):
    connection_id: int | None = None

    def __post_init__(self):
        for field in self.__struct_fields__:
            annotation = self.__annotations__.get(field)
            attr = getattr(self, field)
            if annotation and issubclass(annotation, VecTypes) and not isinstance(attr, annotation):
                setattr(self, field, annotation(*attr))
