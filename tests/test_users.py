def test_create_user(user):
    print('Testing with user', user)
    assert user.username == 'user1'
    assert user.email == 'test@example.com'
