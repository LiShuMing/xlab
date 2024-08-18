import asyncio
import json
import os
from openai import OpenAI


def get_top_hacker_news_stories():
    """Extract top 10 stories from Hacker News using requests and BeautifulSoup"""
    print("Visiting Hacker News...")
    
    # Fallback: Use requests and BeautifulSoup
    print("Using requests and BeautifulSoup to extract stories...")
    import requests
    from bs4 import BeautifulSoup
    
    try:
        response = requests.get("https://news.ycombinator.com/news")
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Find the top stories
        stories = []
        titles = soup.find_all('span', class_='titleline')
        
        for i, title in enumerate(titles[:10]):
            link_tag = title.find('a')
            if link_tag:
                link = link_tag['href']
                # If link is relative, make it absolute
                if link.startswith('//'):
                    link = 'https:' + link
                elif link.startswith('/'):
                    link = 'https://news.ycombinator.com' + link
                story_title = link_tag.text.strip()
            else:
                link = 'N/A'
                story_title = title.text.strip()
                
            stories.append({
                'title': story_title,
                'link': link
            })
        
        return stories
    
    except Exception as e:
        print(f"Error extracting stories: {str(e)}")
        # Return sample stories in case of failure
        return [
            {'title': 'Sample Story 1', 'link': 'https://example.com'},
            {'title': 'Sample Story 2', 'link': 'https://example.com'},
            {'title': 'Sample Story 3', 'link': 'https://example.com'},
            {'title': 'Sample Story 4', 'link': 'https://example.com'},
            {'title': 'Sample Story 5', 'link': 'https://example.com'},
            {'title': 'Sample Story 6', 'link': 'https://example.com'},
            {'title': 'Sample Story 7', 'link': 'https://example.com'},
            {'title': 'Sample Story 8', 'link': 'https://example.com'},
            {'title': 'Sample Story 9', 'link': 'https://example.com'},
            {'title': 'Sample Story 10', 'link': 'https://example.com'},
        ]


def summarize_and_translate_stories(stories):
    """Use LLM to summarize and translate stories to Chinese"""
    print("Summarizing and translating stories...")
    
    # Check if API key is available
    api_key = os.getenv("QWEN_API_KEY") or os.getenv("OPENAI_API_KEY")
    if not api_key or api_key == "your-api-key-here":
        print("WARNING: No API key found. Please set QWEN_API_KEY or OPENAI_API_KEY environment variable.")
        print("For demo purposes, we'll create sample outputs.")
        
        processed_stories = []
        for i, story in enumerate(stories):
            story_title = story.get('title', str(story)[:100])
            sample_output = f"""Original Title: {story_title}

Summary in English: This is a sample summary for demonstration purposes. In a real implementation, Qwen API would provide an actual summary of this news story.

标题 (Title in Chinese): 这是一个示例标题

摘要 (Summary in Chinese): 这是演示目的的示例摘要。在实际实施中，Qwen API将提供此新闻故事的实际摘要。
"""
            processed_stories.append({
                'original': story,
                'summary': sample_output
            })
        return processed_stories
    
    # If we have an API key, use it
    # For Qwen API, we'll use the OpenAI-compatible interface
    base_url = os.getenv("QWEN_API_BASE", "https://dashscope.aliyuncs.com/compatible-mode/v1")
    model_name = os.getenv("MODEL_NAME", "qwen-max")  # Default to Qwen model
    
    # Initialize OpenAI client with Qwen API
    client = OpenAI(
        api_key=api_key,
        base_url=base_url
    )
    
    processed_stories = []
    
    for i, story in enumerate(stories):
        print(f"Processing story {i+1}: {story.get('title', story[:50] if isinstance(story, str) else 'N/A')}")
        
        try:
            # Prepare the prompt for LLM
            story_title = story.get('title', str(story)[:100])
            story_url = story.get('link', 'N/A')
            
            prompt = f"""Please summarize the following news story in 1-2 sentences, then translate both 
            the summary and the title to Chinese. Format your response as follows:
            
            Original Title: {story_title}
            
            Summary in English: [English summary here]
            
            标题 (Title in Chinese): [Translated title here]
            
            摘要 (Summary in Chinese): [Translated summary here]
            """
            
            response = client.chat.completions.create(
                model=model_name,
                messages=[
                    {"role": "user", "content": prompt}
                ],
                max_tokens=500,
                temperature=0.3
            )
            
            summary = response.choices[0].message.content
            
            processed_stories.append({
                'original': story,
                'summary': summary
            })
            
        except Exception as e:
            print(f"Error processing story {i+1}: {str(e)}")
            processed_stories.append({
                'original': story,
                'summary': f"Error processing this story: {str(e)}"
            })
    
    return processed_stories


def main():
    """Main function to run the complete demo"""
    print("Starting Hacker News summarization demo...")
    
    # Step 1: Get top stories from Hacker News
    stories = get_top_hacker_news_stories()
    
    if not stories:
        print("No stories found!")
        return
    
    print(f"Found {len(stories)} stories. Processing now...")
    
    # Step 2: Summarize and translate stories
    processed_stories = summarize_and_translate_stories(stories)
    
    # Step 3: Display results
    print("\n" + "="*80)
    print("HACKER NEWS TOP 10 STORIES SUMMARY (WITH CHINESE TRANSLATION)")
    print("="*80)
    
    for i, processed in enumerate(processed_stories):
        print(f"\n{i+1}. Story:")
        print("-" * 50)
        print(processed['summary'])
        print("-" * 50)
    
    print("\nDemo completed!")


if __name__ == "__main__":
    main()