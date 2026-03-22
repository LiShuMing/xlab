import { config } from "../../../package.json";
import { Document } from "langchain/document";
import LocalStorage from "../localStorage";
import Views from "../views";
import Meet from "./api";
import similarity from 'compute-cosine-similarity';
import { md5 } from "../base";
import { ClaudeClient } from "./ClaudeAPI";

/**
 * Given text and documents, return a list of documents, returning the most similar ones
 * @param queryText 
 * @param docs 
 * @param obj 
 * @returns 
 */
export async function similaritySearch(queryText: string, docs: Document[], obj: { key: string }) {
  const storage = Meet.Global.storage = Meet.Global.storage || new LocalStorage(config.addonRef)
  await storage.lock.promise;
  const embeddings = new Embeddings() as any
  // Search local, to save space, only store vectors
  // The MD5 value is extracted here as verification. 
  // Here local JSON files may become larger and larger 
  var embeddingSource: string = Zotero.Prefs.get(`${config.addonRef}.usingPublisher`) as string
  if (embeddingSource == "Claude-3") {
      const views: Views = Zotero.PapersGPT.views! as Views
      const openaiApiKey: string = views.publisher2models.get("OpenAI")!.apiKey as string
      const geminiApiKey: string = views.publisher2models.get("Gemini")!.apiKey as string
      if (openaiApiKey != null && openaiApiKey.length > 0) {
          embeddingSource = "OpenAI" 
      } else if (geminiApiKey != null && geminiApiKey.length > 0) {
          embeddingSource = "Gemini" 
      } else if (Zotero.isMac) {
          embeddingSource = "Localhost" 
      }
  }
  const id = embeddingSource + ":" + md5(docs.map((i: any) => i.pageContent).join("\n\n"))
  await storage.lock
  const _vv = storage.get(obj, id)
  ztoolkit.log(_vv)
  let vv: any
  if (_vv) {
    Meet.Global.popupWin.createLine({ text: "Reading embeddings...", type: "default" })
    vv = _vv
  } else {
    Meet.Global.popupWin.createLine({ text: "Generating embeddings...", type: "default" })
    vv = await embeddings.embedDocuments(docs.map((i: any) => i.pageContent))
    window.setTimeout(async () => {
      await storage.set(obj, id, vv)
    })
  }

  const v0 = await embeddings.embedQuery(queryText)
  // Find the longest text among the 20 to prevent short but highly similar paragraphs from affecting the accuracy of the answer
  const relatedNumber = Zotero.Prefs.get(`${config.addonRef}.relatedNumber`) as number
  Meet.Global.popupWin.createLine({ text: `Searching ${relatedNumber} related content...`, type: "default" })
  const k = relatedNumber * 5
  const pp = vv.map((v: any) => similarity(v0, v));
  docs = [...pp].sort((a, b) => b - a).slice(0, k).map((p: number) => {
    return docs[pp.indexOf(p)]
  })
  return docs.sort((a, b) => b.pageContent.length - a.pageContent.length).slice(0, relatedNumber)
}


class Embeddings {
  private openaiAPIURL: string = "https://api.openai.com/v1/embeddings"
  private geminiAPIURL: string = "https://generativelanguage.googleapis.com/v1beta/models/text-embedding-004:batchEmbedContents?key="
  private qwenEmbeddingURL: string = "https://dashscope.aliyuncs.com/compatible-mode/v1/embeddings"
  private embeddingAPIURL: string = ""
  constructor() {
  }
  private async request(input: string[]) {
    const views = Zotero.PapersGPT.views as Views
    let api = Zotero.Prefs.get(`${config.addonRef}.usingAPIURL`) as string
    var apiKey = Zotero.Prefs.get(`${config.addonRef}.usingAPIKEY`)
    const split_len: number = Zotero.Prefs.get(`${config.addonRef}.embeddingBatchNum`) as number
    const curPublisher = Zotero.Prefs.get(`${config.addonRef}.usingPublisher`)
    if (curPublisher == "OpenAI") {
      this.embeddingAPIURL = this.openaiAPIURL
    } else if (curPublisher == "Gemini") {
      this.embeddingAPIURL = this.geminiAPIURL
      this.embeddingAPIURL += apiKey
    } else if (curPublisher == "Qwen") {
      // Use Qwen's own embedding API
      this.embeddingAPIURL = this.qwenEmbeddingURL
    } else if (curPublisher == "MiniMax") {
      const openaiApiKey = views.publisher2models.get("OpenAI")!.apiKey
      const geminiApiKey = views.publisher2models.get("Gemini")!.apiKey
      if (openaiApiKey && openaiApiKey.length > 0) {
        this.embeddingAPIURL = this.openaiAPIURL
        apiKey = openaiApiKey
      } else if (geminiApiKey && geminiApiKey.length > 0) {
        this.embeddingAPIURL = this.geminiAPIURL
        this.embeddingAPIURL += geminiApiKey
        apiKey = geminiApiKey
      } else if (Zotero.isMac) {
        this.embeddingAPIURL = "http://localhost:9080/getTextEmbeddings"
      }
    } else if (curPublisher == "Claude-3") {
      // Use minimaxi embedding API with Claude API key
      this.embeddingAPIURL = "https://api.minimaxi.com/v1/embeddings"
      // apiKey is already set from usingAPIKEY
    } else if (curPublisher == "DeepSeek" || curPublisher == "Customized") {
      const openaiApiKey = views.publisher2models.get("OpenAI")!.apiKey
      const geminiApiKey = views.publisher2models.get("Gemini")!.apiKey
      if (openaiApiKey && openaiApiKey.length > 0) {
        this.embeddingAPIURL = this.openaiAPIURL
	apiKey = openaiApiKey
      } else if (geminiApiKey && geminiApiKey.length > 0) {
        this.embeddingAPIURL = this.geminiAPIURL
        this.embeddingAPIURL += geminiApiKey
	apiKey = geminiApiKey
      }	else if (Zotero.isMac) {
        this.embeddingAPIURL = "http://localhost:9080/getTextEmbeddings"
      }
    }

    let res: any

    if (!apiKey && (curPublisher != "DeepSeek" && curPublisher != "MiniMax")) {
      new ztoolkit.ProgressWindow("Error", { closeOtherProgressWindows: true })
        .createLine({ text: "Your apiKey is not configured.", type: "default" })
        .show()
      return
    } else if ((curPublisher == "DeepSeek" || curPublisher == "MiniMax") && this.embeddingAPIURL.length == 0) {
      new ztoolkit.ProgressWindow("Error", { closeOtherProgressWindows: true })
        .createLine({ text: "Embedding requires OpenAI, Gemini API key, or local MCP server on Mac.", type: "default" })
        .show()
      return
    }


    var final_embeddings: number[] = []
    for (let i = 0; i < input.length; i += split_len) {

      const chunk = input.slice(i, i + split_len)
      
       try {
 	if (curPublisher == "OpenAI" || ((curPublisher == "MiniMax" || curPublisher == "DeepSeek" || curPublisher == "Customized") && this.embeddingAPIURL.includes("openai"))) {
          res = await Zotero.HTTP.request(
            "POST",
            this.embeddingAPIURL,
            {
              responseType: "json",
              headers: {
                "Content-Type": "application/json",
                "Authorization": `Bearer ${apiKey}`,
              },
              body: JSON.stringify({
                model: "text-embedding-ada-002",
                input: chunk
              }),
            }
          )
	} else if (curPublisher == "Claude-3" && this.embeddingAPIURL.includes("minimaxi")) {
          // Claude-3 via minimaxi embedding API (OpenAI compatible)
          Zotero.log("[PapersGPT] Calling minimaxi embedding API: " + this.embeddingAPIURL)
          res = await Zotero.HTTP.request(
            "POST",
            this.embeddingAPIURL,
            {
              responseType: "json",
              headers: {
                "Content-Type": "application/json",
                "Authorization": `Bearer ${apiKey}`,
              },
              body: JSON.stringify({
                model: "text-embedding-ada-002",
                input: chunk
              }),
              timeout: 120000
            }
          )
          Zotero.log("[PapersGPT] minimaxi embedding response: " + JSON.stringify(res?.response).substring(0, 200))
	} else if (curPublisher == "Qwen" && this.embeddingAPIURL.includes("dashscope")) {
          // Qwen/DashScope embedding API
          Zotero.log("[PapersGPT] Calling Qwen embedding API: " + this.embeddingAPIURL)
          res = await Zotero.HTTP.request(
            "POST",
            this.embeddingAPIURL,
            {
              responseType: "json",
              headers: {
                "Content-Type": "application/json",
                "Authorization": `Bearer ${apiKey}`,
              },
              body: JSON.stringify({
                model: "text-embedding-v3",
                input: chunk,
                encoding_format: "float"
              }),
              timeout: 120000
            }
          )
          Zotero.log("[PapersGPT] Qwen embedding response: " + JSON.stringify(res?.response).substring(0, 200))
	} else if (curPublisher == "Gemini" || ((curPublisher == "MiniMax" || curPublisher == "Claude-3" || curPublisher == "DeepSeek" || curPublisher == "Customized") && this.embeddingAPIURL.includes("googleapis"))) {
	  var batchRequests = []
	  for (let j = 0; j < split_len; j++) {
            if (i + j >= input.length) break
	    batchRequests.push({
	        model: "models/text-embedding-004",
	        content: {
		    parts: [{
		        text: input[i + j]
		    }]
		}
	    })
	  }
	  res = await Zotero.HTTP.request(
            "POST",
            this.embeddingAPIURL,
            {
              responseType: "json",
              headers: {
                "Content-Type": "application/json",
              },
              body: JSON.stringify({
                requests: batchRequests
              }),
            }
          )
	} else if ((curPublisher == "MiniMax" || curPublisher == "Claude-3" || curPublisher == "DeepSeek" || curPublisher == "Customized") && this.embeddingAPIURL.includes("localhost")) {
	  res = await Zotero.HTTP.request(
            "POST",
            this.embeddingAPIURL,
            {
              responseType: "json",
              headers: {
                "Content-Type": "application/json",
              },
              body: JSON.stringify({
                texts: chunk
              }),
            }
          )
	}
      } catch (error: any) {
        Zotero.log("[PapersGPT] Embedding request failed: " + JSON.stringify(error))
        try {
          error = error.xmlhttp.response?.error
          views.setText(`# ${error.code}\n> \n\n**${error.type}**\n${error.message}`, true)
          new ztoolkit.ProgressWindow(error.code, { closeOtherProgressWindows: true })
            .createLine({ text: error.message, type: "default" })
            .show()
        } catch (e) {
          Zotero.log("[PapersGPT] Embedding error details: " + (error?.message || error))
          new ztoolkit.ProgressWindow("Embedding Error", { closeOtherProgressWindows: true })
            .createLine({ text: error?.message || "Unknown embedding error", type: "default" })
            .show()
        }
      }

      if ((curPublisher == "OpenAI" || ((curPublisher == "MiniMax" || curPublisher == "DeepSeek" || curPublisher == "Customized") && this.embeddingAPIURL.includes("openai"))) && res?.response?.data) {
	final_embeddings = final_embeddings.concat(res.response.data.map((i: any) => i.embedding))
      } else if ((curPublisher == "Claude-3" && this.embeddingAPIURL.includes("minimaxi")) && res?.response?.data) {
        // minimaxi embedding response format is same as OpenAI
	final_embeddings = final_embeddings.concat(res.response.data.map((i: any) => i.embedding))
      } else if ((curPublisher == "Qwen" && this.embeddingAPIURL.includes("dashscope")) && res?.response?.data) {
        // Qwen embedding response format is same as OpenAI
	final_embeddings = final_embeddings.concat(res.response.data.map((i: any) => i.embedding))
      } else if ((curPublisher == "Gemini" || ((curPublisher == "MiniMax" || curPublisher == "DeepSeek" || curPublisher == "Customized") && this.embeddingAPIURL.includes("googleapis"))) && res?.response?.embeddings) {
	final_embeddings = final_embeddings.concat(res.response.embeddings.map((i: any) => i.values))
      } else if ((curPublisher == "MiniMax" || curPublisher == "DeepSeek" || curPublisher == "Customized") && this.embeddingAPIURL.includes("localhost")) {
	final_embeddings = final_embeddings.concat(res.response.Embeddings.map((i: any) => i.values))
      }
    }
    return final_embeddings
  }

  public async embedDocuments(texts: string[]) {
    return await this.request(texts)
  }

  public async embedQuery(text: string) {
    return (await this.request([text]))?.[0]
  }
}


export async function getGPTResponse(requestText: string) {
  const usingPublisher = Zotero.Prefs.get(`${config.addonRef}.usingPublisher`)
 
  if (usingPublisher == "Local LLM") {
      return await getResponseByLocalLLM(requestText) 
  }
      
  return await getResponseByOnlineModel(requestText) 
}

export async function getResponseByOnlineModel(requestText: string) {
  const views = Zotero.PapersGPT.views as Views
  const apiKey: string = Zotero.Prefs.get(`${config.addonRef}.usingAPIKEY`) as string
  const temperature = Zotero.Prefs.get(`${config.addonRef}.temperature`)
  let apiURL: string = Zotero.Prefs.get(`${config.addonRef}.usingAPIURL`) as string
  const model: string = Zotero.Prefs.get(`${config.addonRef}.usingModel`) as string
  const curPublisher = Zotero.Prefs.get(`${config.addonRef}.usingPublisher`) as string

  // Force correct API URL for Claude-3 (minimaxi proxy)
  if (curPublisher === "Claude-3") {
    apiURL = "https://api.minimaxi.com/anthropic/v1/messages"
  }

  Zotero.log("=== API Request Debug ===")
  Zotero.log("Publisher: " + curPublisher)
  Zotero.log("API Key length: " + (apiKey ? apiKey.length : 0))
  Zotero.log("API Key prefix: " + (apiKey ? apiKey.substring(0, 8) + "..." : "null"))
  Zotero.log("API URL: " + apiURL)
  Zotero.log("Model: " + model)
  Zotero.log("Request text preview: " + requestText.substring(0, 200))

  // Check if template pattern exists and needs processing
  if (requestText.includes("${") && requestText.includes("getRelatedText")) {
    Zotero.log("[PapersGPT] Template detected, calling getRelatedText directly...")
    try {
      // Extract the input from the template
      const inputMatch = requestText.match(/getRelatedText\(([^)]+)\)/)
      let inputText = "Summary" // Default
      if (inputMatch && inputMatch[1]) {
        // Try to evaluate the input expression
        try {
          inputText = await window.eval(inputMatch[1])
        } catch (e) {
          Zotero.log("[PapersGPT] Could not eval input: " + e)
        }
      }
      Zotero.log("[PapersGPT] Calling getRelatedText with: " + inputText)

      // Import and call getRelatedText
      const { getRelatedText } = await import("./Meet/Zotero")
      const relatedText = await getRelatedText(inputText)
      Zotero.log("[PapersGPT] getRelatedText result length: " + (relatedText?.length || 0))

      if (relatedText && relatedText.length > 0) {
        // Replace the template with the result
        const templatePattern = /\$\{[\s\S]+?getRelatedText\([\s\S]+?\)[\s\S]*?\}/
        requestText = requestText.replace(templatePattern, relatedText)
        Zotero.log("[PapersGPT] After template replacement: " + requestText.substring(0, 200))
      }
    } catch (e) {
      Zotero.log("[PapersGPT] Template processing failed: " + e)
    }
  }

  if (!apiKey || apiKey.length === 0) {
    views.setText("# Error\nAPI key is empty! Please set your API key in the settings.", true)
    return
  }
  views.messages.push({
    role: "user",
    content: requestText
  })
  const deltaTime = Zotero.Prefs.get(`${config.addonRef}.deltaTime`) as number
  // Store the last results
  let _textArr: string[] = []
  // Changes in real time as requests return
  let textArr: string[] = []
  // Activate output
  views.stopAlloutput()
  views.setText("")
  let responseText: string | undefined
  const id: number = window.setInterval(async () => {
    if (!responseText && _textArr.length == textArr.length) { return}
    _textArr = textArr.slice(0, _textArr.length + 1)
    let text = _textArr.join("")
    text.length > 0 && views.setText(text)
    if (responseText && responseText == text) {
      views.setText(text, true)
      window.clearInterval(id)
    }
  }, deltaTime)
  views._ids.push({
    type: "output",
    id: id
   })
   const chatNumber = Zotero.Prefs.get(`${config.addonRef}.chatNumber`) as number

     if (curPublisher == "OpenAI" || curPublisher == "DeepSeek" || curPublisher == "Customized" || curPublisher == "Qwen") {
    try {
      var deployedModel = model
      if (model.includes(":")) {
          let index: number = model.indexOf(":")
          deployedModel = model.substr(index + 1, model.length)
      }

       await Zotero.HTTP.request(
        "POST",
        apiURL,
        {
          headers: {
            "Content-Type": "application/json",
            "Authorization": `Bearer ${apiKey}`,
          },
          body: JSON.stringify({
            model: deployedModel,
            messages: views.messages.slice(-chatNumber),
            stream: true,
            temperature: Number(temperature)
          }),
          responseType: "text",
          timeout: 180000,
          requestObserver: (xmlhttp: XMLHttpRequest) => {
            Zotero.log("Request headers: " + xmlhttp.getAllResponseHeaders())
            xmlhttp.onprogress = (e: any) => {
              try {
                textArr = e.target.response.match(/data: (.+)/g).filter((s: string) => s.indexOf("content") >= 0).map((s: string) => {
                  try {
                    return JSON.parse(s.replace("data: ", "")).choices[0].delta.content.replace(/\n+/g, "\n")
                  } catch {
                    return false
                  }
                }).filter(Boolean)
              } catch {
		// Changes in real time as requests return
                ztoolkit.log(e.target.response)
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
        error = JSON.parse(error?.xmlhttp?.response).error
        textArr = [`# ${error.code}\n> ${apiURL}\n\n**${error.type}**\n${error.message}`]
        new ztoolkit.ProgressWindow(error.code, { closeOtherProgressWindows: true })
          .createLine({ text: error.message, type: "default" })
          .show()
      } catch {
        new ztoolkit.ProgressWindow("Error", { closeOtherProgressWindows: true })
          .createLine({ text: error.message, type: "default" })
          .show()
      }
    }
  } else if (curPublisher == "Gemini") {

    var deployedModel = model
    if (model.includes(":")) {
        let index = model.indexOf(":")
        deployedModel = model.substr(index + 1, model.length)  		   
    }

    const index = apiURL.lastIndexOf("/")
    apiURL = apiURL.substr(0, index)
    apiURL = apiURL + "/" + deployedModel + ":streamGenerateContent?alt=sse&key=" + apiKey
    var text = ""
    if (views.messages.slice(-1)[0].role == "user") {
      text = views.messages.slice(-1)[0].content 
    } else if (views.messages.slice(-2, -1)[0].role == "user") {
      text = views.messages.slice(-2, -1)[0].content 
    }
    var requestParameters = [{
      parts: [{
        text: text 
      }]
    }] 
    
    try {
      await Zotero.HTTP.request(
	"POST",
        apiURL,
        {
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            contents: requestParameters,
          }),
          responseType: "text",
          requestObserver: (xmlhttp: XMLHttpRequest) => {
            xmlhttp.onprogress = (e: any) => {
              try {
                textArr = e.target.response.match(/data: (.+)/g).filter((s: string) => s.indexOf("content") >= 0).map((s: string) => {
                  try {
                    return JSON.parse(s.replace("data: ", "")).candidates[0].content.parts[0].text.replace(/\n+/g, "\n")
                  } catch {
                    return false
                  }
                }).filter(Boolean)
              } catch {
                // The error usually occurs when the token exceeds the limit
                ztoolkit.log(e.target.response)
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
        error = JSON.parse(error?.xmlhttp?.response).error
        textArr = [`# ${error.code}\n> ${apiURL}\n\n**${error.type}**\n${error.message}`]
        new ztoolkit.ProgressWindow(error.code, { closeOtherProgressWindows: true })
          .createLine({ text: error.message, type: "default" })
          .show()
      } catch {
        new ztoolkit.ProgressWindow("Error", { closeOtherProgressWindows: true })
          .createLine({ text: error.message, type: "default" })
          .show()
      }
    }
  } else if (curPublisher == "MiniMax") {
    try {
      var deployedModel = model
      if (model.includes(":")) {
          let index: number = model.indexOf(":")
          deployedModel = model.substr(index + 1, model.length)
      }
      await Zotero.HTTP.request(
        "POST",
        apiURL,
        {
          headers: {
            "Content-Type": "application/json",
            "Authorization": `Bearer ${apiKey}`,
          },
          body: JSON.stringify({
            model: deployedModel,
            messages: views.messages.slice(-chatNumber).map((msg: any) => ({
              role: msg.role,
              content: msg.content
            })),
            stream: true,
            temperature: Number(temperature),
            max_output_tokens: 2048
          }),
          responseType: "text",
          requestObserver: (xmlhttp: XMLHttpRequest) => {
            xmlhttp.onprogress = (e: any) => {
              try {
                textArr = e.target.response.match(/data: (.+)/g).filter((s: string) => s.indexOf("content") >= 0).map((s: string) => {
                  try {
                    return JSON.parse(s.replace("data: ", "")).choices[0].delta.content.replace(/\n+/g, "\n")
                  } catch {
                    return false
                  }
                }).filter(Boolean)
              } catch {
                ztoolkit.log(e.target.response)
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
        error = JSON.parse(error?.xmlhttp?.response).error
        textArr = [`# ${error.code}\n> ${apiURL}\n\n**${error.type}**\n${error.message}`]
        new ztoolkit.ProgressWindow(error.code, { closeOtherProgressWindows: true })
          .createLine({ text: error.message, type: "default" })
          .show()
      } catch {
        new ztoolkit.ProgressWindow("Error", { closeOtherProgressWindows: true })
          .createLine({ text: error.message, type: "default" })
          .show()
      }
    }
  } else if (curPublisher == "Claude-3") {
    try {
      // Use the new Anthropic SDK-based Claude client
      const claudeClient = new ClaudeClient(apiKey, apiURL)
      
      // Prepare messages for the API
      const messages = views.messages.slice(-chatNumber).map((msg: any) => ({
        role: msg.role,
        content: msg.content
      }))

      // Extract deployed model name
      var deployedModel = model
      if (model.includes(":")) {
        let index = model.indexOf(":")
        deployedModel = model.substr(index + 1, model.length)
      }

      // Create a buffer to accumulate streaming response
      let responseBuffer = ""
      
      // Make the streaming request
      responseText = await claudeClient.stream(
        messages,
        deployedModel,
        2048,
        (chunk: string) => {
          // Update the text array for real-time display
          textArr.push(chunk)
        }
      )
      
      Zotero.log("[PapersGPT] Claude API response completed, length: " + responseText.length)
      
    } catch (error: any) {
      try {
        textArr = [`# Error\n> ${apiURL}\n\n**Claude API Error**\n${error.message}`]
        new ztoolkit.ProgressWindow("Error", { closeOtherProgressWindows: true })
          .createLine({ text: error.message, type: "default" })
          .show()
      } catch {
        new ztoolkit.ProgressWindow("Error", { closeOtherProgressWindows: true })
          .createLine({ text: error.message || "Unknown error", type: "default" })
          .show()
      }
    }
  } 
  
  responseText = textArr.join("")
  ztoolkit.log("responseText", responseText)
  views.messages.push({
    role: "assistant",
    content: responseText
  })
  return responseText
}

export async function getResponseByLocalLLM(requestText: string) {
  const publisher = Zotero.Prefs.get(`${config.addonRef}.usingPublisher`) as string
  if (publisher != "Local LLM") {
      return
  } 
  const views = Zotero.PapersGPT.views as Views
  const temperature = Zotero.Prefs.get(`${config.addonRef}.temperature`)
  const apiURL = Zotero.Prefs.get(`${config.addonRef}.usingAPIURL`) as string
  const model = Zotero.Prefs.get(`${config.addonRef}.usingModel`) as string
  views.messages.push({
    role: "user",
    content: requestText
  })
  const deltaTime = Zotero.Prefs.get(`${config.addonRef}.deltaTime`) as number
  // Store the last results 
  let _textArr: string[] = []
  // Changes in real time as requests return
  let textArr: string[] = []
  // Activate output 
  views.stopAlloutput()
  views.setText("")
  let responseText: string | undefined
  const id: number = window.setInterval(async () => {
    if (!responseText && _textArr.length == textArr.length) { return}
    _textArr = textArr.slice(0, _textArr.length + 1)
    let text = _textArr.join("")
    text.length > 0 && views.setText(text)
    if (responseText && responseText == text) {
      views.setText(text, true)
      window.clearInterval(id)
    }
  }, deltaTime)
  views._ids.push({
    type: "output",
    id: id
  })
  const chatNumber = Zotero.Prefs.get(`${config.addonRef}.chatNumber`) as number
  var responseTimeout = 60000 * 3
  if (model == "QwQ-32B-Preview" || model == "marco-o1") {
    responseTimeout = 10 * 60000
  }

  try {
    await Zotero.HTTP.request(
      "POST",
      apiURL,
      {
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          model: model,
          messages: views.messages.slice(-chatNumber),
          stream: true,
          temperature: Number(temperature)
        }),
        responseType: "text",
        requestObserver: (xmlhttp: XMLHttpRequest) => {
          xmlhttp.onprogress = (e: any) => {
            try {
              textArr = e.target.response.match(/data: (.+)/g).filter((s: string) => s.indexOf("content") >= 0).map((s: string) => {
                try {
                  return JSON.parse(s.replace("data: ", "")).choices[0].delta.content.replace(/\n+/g, "\n")
                } catch {
                  return false
                }
              }).filter(Boolean)
            } catch {
              // The error usually occurs when the token exceeds the limit
              ztoolkit.log(e.target.response)
	      Zotero.log(e.target.response)
            }
            if (e.target.timeout) {
              e.target.timeout = 0;
            }
          };
        },
	timeout: responseTimeout
      }
    );
  } catch (error: any) {
    try {
      error = JSON.parse(error?.xmlhttp?.response).error
      textArr = [`# ${error.code}\n> ${apiURL}\n\n**${error.type}**\n${error.message}`]
      new ztoolkit.ProgressWindow(error.code, { closeOtherProgressWindows: true })
        .createLine({ text: error.message, type: "default" })
        .show()
    } catch {
      new ztoolkit.ProgressWindow("Error", { closeOtherProgressWindows: true })
        .createLine({ text: error.message, type: "default" })
        .show()
    }
  }
  responseText = textArr.join("")
  views.messages.push({
    role: "assistant",
    content: responseText
  })
  return responseText
}


