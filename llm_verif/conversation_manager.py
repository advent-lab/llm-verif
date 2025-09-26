from transformers import PreTrainedTokenizerBase

class ConversationManager:

    def __init__(self, tokenizer: PreTrainedTokenizerBase, system_prompt: str, max_input_tokens: int = 15000):
        self.tokenizer: PreTrainedTokenizerBase = tokenizer
        self.max_input_tokens = max_input_tokens
        self.conversation = [{"role": "system", "content": system_prompt}]
        self.stack_pointer = 1

    def length(self):
        return len(self.conversation)

    def append_user_message(self, message: str, update_stack_pointer: bool = False):

        assert self.conversation[-1]["role"] == "assistant" or self.conversation[-1]["role"] == "system" , "Cannot append a user message to a user message."

        self.conversation.append({"role": "user", "content": message})

        if update_stack_pointer:
            self.stack_pointer = len(self.conversation) - 1

    def append_assistant_message(self, message: str, slice: bool = False):

        assert self.conversation[-1]["role"] == "user", "Cannot append an assistant message to an assistant message."

        self.conversation.append({"role": "assistant", "content": message})

        if slice:
            self.slice_from_stack_pointer()

    def update_system_prompt(self, system_prompt: str):
        self.conversation[0]["content"] = system_prompt

    def _token_count(self, prompt: str):
        return len(self.tokenizer(prompt, return_tensors="pt")["input_ids"][0]) # type: ignore
    
    def _prune_to_fit(self, prompt: str):
        while self._token_count(prompt) > self.max_input_tokens and len(self.conversation) > 2:
            self.conversation.pop(1)
            self.conversation.pop(1)
            prompt = self._build_prompt()
            self.stack_pointer = 1

        return prompt

    def _build_prompt(self):
        return self.tokenizer.apply_chat_template(
            self.conversation,
            tokenize=False,
            add_generation_prompt=True
        )
    
    def get_prompt(self):
        prompt = self._build_prompt()
        return self._prune_to_fit(prompt)
    
    def get_messages(self):
        _ = self._prune_to_fit(self._build_prompt())

        return self.conversation
    
    def _set_stack_pointer(self):
        self.stack_pointer = len(self.conversation) - 1

    def slice_from_stack_pointer(self):

        # For a slice operation to be valid, stack pointer must be pointing at a User message
        assert self.conversation[self.stack_pointer]["role"] == "user", "Stack pointer must be pointing at a user message to slice the conversation."

        # Most recent message must be an assistant message
        assert self.conversation[-1]["role"] == "assistant", "Most recent message must be an assistant message to slice the conversation."

        self.conversation = self.conversation[:self.stack_pointer + 1] + [self.conversation[-1]]

        self.stack_pointer = len(self.conversation) - 2
    
    def __str__(self):
        return self.get_prompt()
