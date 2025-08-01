def test_buyer_matchmaker_agent(mocker):
    # Mock the Weaviate client
    mocker.patch('src.core.vector_db.client.WeaviateClient.vector_search', return_value=[])
    
    # ... test the agent's logic ...
