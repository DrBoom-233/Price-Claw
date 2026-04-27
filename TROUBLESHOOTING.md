1. 复用schema之后，还是调用了LLM，逻辑应该改成如果提取成功，就不调用LLM
2. 价格信息输出应该到两个地方，一个是mongoDB，一个是price_info_output