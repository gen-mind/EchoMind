Inside src there is a folder "proto" with two subfolders: 
- public, will contain the proto definition for object exposed by the APIs and used by the client
- internal, will contain all proto definition for onject used internally
The CI, when needed will create the typescript definition of the proto object or the pydantic to reduce errors and increase productivity 

