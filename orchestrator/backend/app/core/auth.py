from fastapi import Header, HTTPException, status

def require_producer(x_user_role: str = Header(..., description="Role required: PRODUCER or AUDITOR")):
    if x_user_role.upper() != "PRODUCER":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: Requires PRODUCER role to mutate master footprints."
        )
    return x_user_role


def require_auditor(x_user_role: str = Header(..., description="Role required: PRODUCER or AUDITOR")):
    if x_user_role.upper() != "AUDITOR":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: Requires AUDITOR role to execute piracy inference models."
        )
    return x_user_role
