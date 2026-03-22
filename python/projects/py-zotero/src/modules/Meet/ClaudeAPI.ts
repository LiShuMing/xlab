import Anthropic from "@anthropic-ai/sdk";
import { config } from "../../../package.json";

/**
 * Claude API client using Anthropic SDK
 * Provides both SDK-based and HTTP-based fallback for Zotero plugin compatibility
 */
export class ClaudeClient {
  // Use any type to bypass SDK type issues in Zotero environment
  private client: any = null;
  private apiKey: string = "";
  private apiUrl: string = "https://api.minimaxi.com/anthropic/v1/messages";
  private useSDK: boolean = true;

  constructor(apiKey: string = "", apiUrl: string = "") {
    this.apiKey = apiKey;
    if (apiUrl && apiUrl.length > 0) {
      this.apiUrl = apiUrl;
    }
    this.initializeClient();
  }

  /**
   * Initialize the Anthropic client
   * Falls back to HTTP mode if SDK cannot be used in the environment
   */
  private initializeClient(): void {
    try {
      // Check if we're in a environment that supports the Anthropic SDK
      // The SDK requires Web Streams and modern fetch which may not be available in Zotero
      if (this.apiKey && this.apiKey.length > 0) {
        // Try to initialize with a custom fetch to handle the proxy URL
        this.client = new Anthropic.Anthropic({
          apiKey: this.apiKey,
          baseURL: this.apiUrl.replace("/v1/messages", ""),
        });
        this.useSDK = true;
        Zotero.log("[PapersGPT] Claude client initialized with Anthropic SDK");
      }
    } catch (error) {
      Zotero.log("[PapersGPT] Failed to initialize Anthropic SDK, falling back to HTTP: " + error);
      this.useSDK = false;
    }
  }

  /**
   * Update API credentials
   */
  public updateCredentials(apiKey: string, apiUrl?: string): void {
    this.apiKey = apiKey;
    if (apiUrl && apiUrl.length > 0) {
      this.apiUrl = apiUrl;
    }
    this.initializeClient();
  }

  /**
   * Get available models
   */
  public getModels(): string[] {
    return [
      "claude-sonnet-4-20250514",
      "claude-opus-4-20250514",
      "claude-3-5-sonnet-20241022",
      "claude-3-haiku-20240307"
    ];
  }

  /**
   * Make a streaming request to Claude API using the SDK
   */
  public async *streamWithSDK(
    messages: Array<{ role: string; content: string }>,
    model: string,
    maxTokens: number = 2048,
    onProgress?: (text: string) => void
  ): AsyncGenerator<string> {
    if (!this.client) {
      throw new Error("Claude client not initialized");
    }

    try {
      const response = await this.client.messages.stream({
        model: model,
        max_tokens: maxTokens,
        messages: messages.map(msg => ({
          role: msg.role as "user" | "assistant",
          content: msg.content
        })),
      });

      for await (const event of response) {
        if (event.type === "content_block_delta" && event.delta.type === "text_delta") {
          const text = event.delta.text;
          if (onProgress) {
            onProgress(text);
          }
          yield text;
        }
      }
    } catch (error) {
      Zotero.log("[PapersGPT] SDK streaming error: " + error);
      throw error;
    }
  }

  /**
   * Make a streaming request to Claude API using HTTP fallback
   * Compatible with Zotero's environment and proxy URLs
   */
  public async streamWithHTTP(
    messages: Array<{ role: string; content: string }>,
    model: string,
    maxTokens: number = 2048,
    onProgress?: (text: string) => void
  ): Promise<string> {
    const temperature = Zotero.Prefs.get(`${config.addonRef}.temperature`) as number;
    const chatNumber = Zotero.Prefs.get(`${config.addonRef}.chatNumber`) as number;
    const deltaTime = Zotero.Prefs.get(`${config.addonRef}.deltaTime`) as number;

    // Store the last results
    let _textArr: string[] = [];
    // Changes in real time as requests return
    let textArr: string[] = [];

    // Extract deployed model name
    var deployedModel = model;
    if (model.includes(":")) {
      let index = model.indexOf(":");
      deployedModel = model.substr(index + 1, model.length);
    }

    try {
      await Zotero.HTTP.request(
        "POST",
        this.apiUrl,
        {
          headers: {
            "x-api-key": `${this.apiKey}`,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
            "anthropic-beta": "messages-2023-12-15"
          },
          body: JSON.stringify({
            model: deployedModel,
            max_tokens: maxTokens,
            messages: messages.slice(-chatNumber),
            stream: true,
            temperature: temperature
          }),
          responseType: "text",
          timeout: 180000,
          requestObserver: (xmlhttp: XMLHttpRequest) => {
            xmlhttp.onprogress = (e: any) => {
              try {
                textArr = e.target.response.match(/data: (.+)/g)
                  ?.filter((s: string) => s.indexOf("content_block_delta") >= 0)
                  .map((s: string) => {
                    try {
                      return JSON.parse(s.replace("data: ", "")).delta.text.replace(/\n+/g, "\n");
                    } catch {
                      return false;
                    }
                  })
                  .filter(Boolean) || [];
              } catch {
                Zotero.log("[PapersGPT] HTTP streaming error: " + e.target.response);
              }
              if (e.target.timeout) {
                e.target.timeout = 0;
              }
            };
          },
        }
      );
    } catch (error: any) {
      try {
        const parsedError = JSON.parse(error?.xmlhttp?.response)?.error;
        throw new Error(`${parsedError?.code}: ${parsedError?.message}`);
      } catch {
        throw new Error(error.message || "Unknown error");
      }
    }

    return textArr.join("");
  }

  /**
   * Unified streaming method - chooses between SDK and HTTP based on availability
   */
  public async stream(
    messages: Array<{ role: string; content: string }>,
    model: string,
    maxTokens: number = 2048,
    onProgress?: (text: string) => void
  ): Promise<string> {
    if (this.useSDK && this.client) {
      try {
        let fullResponse = "";
        for await (const chunk of this.streamWithSDK(messages, model, maxTokens, onProgress)) {
          fullResponse += chunk;
        }
        return fullResponse;
      } catch (error) {
        Zotero.log("[PapersGPT] SDK failed, falling back to HTTP: " + error);
        return this.streamWithHTTP(messages, model, maxTokens, onProgress);
      }
    } else {
      return this.streamWithHTTP(messages, model, maxTokens, onProgress);
    }
  }

  /**
   * Non-streaming request for simple queries
   */
  public async complete(
    messages: Array<{ role: string; content: string }>,
    model: string,
    maxTokens: number = 2048
  ): Promise<string> {
    if (this.useSDK && this.client) {
      try {
        const response = await this.client.messages.create({
          model: model,
          max_tokens: maxTokens,
          messages: messages.map(msg => ({
            role: msg.role as "user" | "assistant",
            content: msg.content
          })),
        });

        return response.content[0].type === "text" ? response.content[0].text : "";
      } catch (error) {
        Zotero.log("[PapersGPT] SDK completion error, falling back to HTTP: " + error);
        return this.streamWithHTTP(messages, model, maxTokens);
      }
    } else {
      return this.streamWithHTTP(messages, model, maxTokens);
    }
  }
}

/**
 * Get the default Claude API configuration
 */
export function getDefaultClaudeConfig(): {
  models: string[];
  apiUrl: string;
  hasApiKey: boolean;
} {
  return {
    models: [
      "claude-sonnet-4-20250514",
      "claude-opus-4-20250514",
      "claude-3-5-sonnet-20241022",
      "claude-3-haiku-20240307"
    ],
    apiUrl: "https://api.minimaxi.com/anthropic/v1/messages",
    hasApiKey: true
  };
}
