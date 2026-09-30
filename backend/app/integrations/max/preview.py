class PreviewMaxClient:
    """Local demonstration sink; never sends requests to MAX."""
    async def send(self,text,**kwargs):return {"message":{"body":{"mid":"local-preview"}}}
