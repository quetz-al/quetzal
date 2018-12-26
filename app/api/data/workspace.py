def fetch():
    """ List workspaces


    Returns
    -------
    list
        List of Workspace details as a dictionaries

    """
    return [{
        'id': i,
    } for i in range(10)]

