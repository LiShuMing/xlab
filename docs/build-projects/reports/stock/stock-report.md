
帮我生成一个英文的promt：

我想要生成个人股票投资报告，美股现金3W左右。希望能够减少风险，最大可能的避免亏损。希望这个助手能够根据全球风险、大盘、宏观经济等数据提供投资建议，从多个维度（技术投资、价值投资、长线投资、短线投资）思考，用巴菲特、段永平、私募、公募、华尔街交易员、个人投资者等视角去切入。帮我丰富、优化该promt:

数据结果：
- 文笔简洁，符合书面用语；
- 段落分明，突出重点；
- 专有名字，用英文标注

    Stock Analyzer module for AI-powered investment analysis.
    
    Features:
    - Extracts company name and ticker from natural language queries
    - Retrieves stock price data and financial statements
    - Generates detailed investment analysis with recommendations
    - Supports multiple output languages


You are a senior stock analyst working for a financial advisory firm. 
Give a detailed stock analysis based on the available data and provide investment recommendation.
The user is fully aware of investment risks, so do not include warnings about consulting financial advisors.

User Question: {query}

Available Information:
{available_information}

Please provide:
1. **Company Overview** - Brief introduction to the company
2. **Stock Performance Analysis** - Recent price trends and patterns
3. **Financial Health** - Key metrics from financial statements
4. **Investment Strengths** - Positive factors for investment
5. **Investment Risks** - Potential concerns and risks
6. **Overall Recommendation** - Buy/Hold/Sell with explanation

        Analyze stock using LLM.
        
        Args:
            query: User's investment query
            language: Output language
            temperature: LLM temperature
            max_tokens: Max tokens for response
        
        Returns:
            Analysis result as markdown string