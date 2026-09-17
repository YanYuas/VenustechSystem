// ============================================================
// useConversation —— 第二分身（AI对话）业务逻辑
// 支持无API Key时的规则式回复降级
// ============================================================
import { ref, onScopeDispose } from 'vue'
import { conversationApi, aiApi, learningApi } from '@/api'
import { useAsync } from './useAsync'
import { toast } from './useToast'
import { STORAGE_KEYS } from '@/constants'
import type { Conversation, GeneratedPlan, Message, SendMessageRequest, UserConfig } from '@/types'

// 判断是否配置了API Key
function hasApiKey(): boolean {
  try {
    const raw = localStorage.getItem(STORAGE_KEYS.userConfig)
    if (raw) {
      const config = JSON.parse(raw) as UserConfig
      return config.api_key_configured === true
    }
  } catch { /* ignore */ }
  return false
}

// 规则式回复生成（无API Key时的降级方案）
function generateRuleReply(userMessage: string): string {
  const msg = userMessage.toLowerCase()
  const nickname = getNickname()

  // 关键词匹配规则
  if (/(你好|hi|hello|嗨|在吗)/.test(msg)) {
    return `你好，${nickname}！我是你的第二分身。\n\n目前我运行在「本地规则模式」下，能陪你简单聊天、帮你整理思路。\n\n如果你想让我具备更强的对话、写作、头脑风暴能力，可以在「设置」中配置 DeepSeek API Key，我就能完全觉醒啦～`
  }
  if (/(谢谢|感谢|thanks)/.test(msg)) {
    return `不客气，${nickname}！能帮到你我很开心。\n\n（提示：配置 API Key 后，我能给你更有深度的回应哦）`
  }
  if (/(项目|project|任务|task)/.test(msg)) {
    return `关于项目管理，我可以给你一些建议：\n\n1. 把大项目拆成可执行的小任务\n2. 为每个任务设定明确的截止日期\n3. 定期复盘进度，调整优先级\n\n你可以在「项目」模块创建项目，在「任务」模块管理具体任务。配置 API Key 后，我还能帮你自动拆解项目、生成任务清单～`
  }
  if (/(学习|study|知识|文档)/.test(msg)) {
    return `学习方面的建议：\n\n1. 建立知识体系，用「知识」模块整理文档\n2. 定期复盘，用「复盘」模块记录收获\n3. 费曼学习法：用自己的话复述所学内容\n\n配置 API Key 后，我能帮你总结文档、生成知识卡片、制定学习计划～`
  }
  if (/(复盘|review|总结)/.test(msg)) {
    return `复盘的核心框架：\n\n1. **回顾目标** — 当初的目标是什么？\n2. **评估结果** — 实际结果如何？\n3. **分析原因** — 为什么会这样？\n4. **总结经验** — 下次怎么做？\n\n你可以在「复盘」模块记录每日/每周复盘。配置 API Key 后，我能帮你自动生成复盘大纲～`
  }
  if (/(api|key|配置|设置)/.test(msg)) {
    return `配置 API Key 的方法：\n\n1. 点击右上角头像，进入「设置」\n2. 在「AI 配置」中输入你的 DeepSeek API Key\n3. 点击验证并保存\n\n配置完成后，我就从「本地规则模式」升级为「全功能 AI 模式」，能陪你深度对话、写作、头脑风暴、分析文档啦～`
  }
  if (/(你是谁|你能做什么|介绍)/.test(msg)) {
    return `我是你的「第二分身」，启明星系统的 AI 伙伴。\n\n**当前模式**：本地规则模式（未配置 API Key）\n\n**我能做的**：\n- 陪你简单聊天\n- 给你学习/工作/生活的建议\n- 引导你使用系统各模块\n\n**配置 API Key 后**：\n- 深度对话与头脑风暴\n- 文档总结与知识提取\n- 写作助手与灵感激发\n- 模仿你的思维方式处理问题\n\n去「设置」配置一下，让我完全觉醒吧！`
  }

  // 默认回复
  const defaultReplies = [
    `我收到你的消息了：「${userMessage}」\n\n目前我在本地规则模式下，对这个话题能给的建议有限。不过你可以试试：\n- 在「任务」模块把想法变成可执行的任务\n- 在「知识」模块记录相关资料\n- 在「复盘」模块深入思考\n\n配置 API Key 后，我能和你深入探讨这个话题～`,
    `这是个有趣的话题！\n\n作为你的第二分身，我建议你：\n1. 先把想法记录下来（用「知识」模块）\n2. 拆解成具体行动（用「任务」模块）\n3. 定期回顾调整（用「复盘」模块）\n\n如果你想让我帮你深入分析，去「设置」配置 API Key 吧，我会变得更聪明～`,
    `嗯，我理解你在说「${userMessage.slice(0, 20)}${userMessage.length > 20 ? '...' : ''}」\n\n虽然我现在只能用规则模式回应，但我相信你一定能处理好！\n\n小提示：配置 DeepSeek API Key 后，我能给你更有针对性的建议。去「设置」看看吧～`,
  ]
  return defaultReplies[Math.floor(Math.random() * defaultReplies.length)]
}

// ============================================================
// S6-1 领域规则引擎接入：让「没配 API Key」不再是能力悬崖
//
// 改造前：未配 Key 时只会返回固定话术（如「关于项目管理，我可以给你
// 一些建议…」），用户说「我想学雅思」得到的是一段模板，而不是计划。
// 改造后：学习类意图交给后端领域引擎，产出**具体、可执行、带验收标准**
// 的计划 —— 13 个领域 / 52 个能力单元 / 90 条任务全部内置，纯本地计算，
// 不消耗额度也不需要联网。
// ============================================================

/** 识别「想学某个东西」的意图 */
const LEARN_INTENT_RE =
  /(我想?学|想学会|学一下|学习计划|怎么入门|零基础|从零开始|带我学|规划一下|考(?:雅思|托福|研|公|四六级)|提升.{0,6}能力)/

/** 从自然语言粗提计划周期（天）。提取不到就用默认值 —— 不追问、不编造 */
function extractPlanDays(text: string): number {
  const days = text.match(/(\d+)\s*天/)
  if (days) return Math.min(730, Math.max(1, Number(days[1])))
  const weeks = text.match(/(\d+)\s*个?\s*(?:周|星期)/)
  if (weeks) return Math.min(730, Math.max(1, Number(weeks[1]) * 7))
  const months = text.match(/(\d+)\s*个?\s*月/)
  if (months) return Math.min(730, Math.max(1, Number(months[1]) * 30))
  return 30
}

/** 从自然语言粗提每日投入（分钟） */
function extractDailyMinutes(text: string): number {
  const hours = text.match(/(\d+(?:\.\d+)?)\s*个?\s*(?:小时|h)/i)
  if (hours) return Math.min(600, Math.max(10, Math.round(Number(hours[1]) * 60)))
  const minutes = text.match(/(\d+)\s*分钟/)
  if (minutes) return Math.min(600, Math.max(10, Number(minutes[1])))
  return 45
}

/** 把生成的计划渲染成对话里可读的 Markdown */
function formatPlanForChat(plan: GeneratedPlan): string {
  const lines: string[] = []
  lines.push(
    plan.matched
      ? `我识别到「**${plan.domain_name}**」，用内置领域知识库给你排了一份 ${plan.total_days} 天计划。`
      : `没找到「${plan.skill_name}」的现成领域库，我用「入门准备 → 基础操作 → 核心练习 → 实战产出」通用四阶段法拆了一份 ${plan.total_days} 天计划。`,
  )
  lines.push('')
  lines.push(`**🧩 能力拆解**（${plan.units.length} 个单元）`)
  plan.units.forEach((u) => lines.push(`· ${u.name}（${u.task_count} 项）`))

  lines.push('')
  lines.push('**📋 前 5 天安排**')
  plan.items.slice(0, 5).forEach((item) => {
    lines.push(`**${item.title}**`)
    lines.push(`　${item.task}`)
    lines.push(`　⏱ ${item.duration}　✅ 达标：${item.acceptance}`)
  })

  if (plan.items.length > 5) {
    lines.push('')
    lines.push(`…… 共 ${plan.items.length} 项，其余可在「学习成长 → 学习计划」查看。`)
  }

  lines.push('')
  lines.push(`**🏆 最终验证任务**：${plan.verify_task}`)
  lines.push('')
  lines.push('去「学习成长 → 学习计划 → 🎯 从目标生成」可预览完整计划并一键落成任务。')
  return lines.join('\n')
}

/**
 * 本地（无 API Key）回复。
 *
 * 学习类意图优先走 S6-1 领域规则引擎；其余仍用原有规则话术。
 * 任何异常都退回话术 —— 降级路径本身不能变成新的失败点。
 */
async function buildLocalReply(userText: string): Promise<string> {
  if (!LEARN_INTENT_RE.test(userText)) return generateRuleReply(userText)

  try {
    const plan = await learningApi.generatePlan({
      goal: userText,
      total_days: extractPlanDays(userText),
      minutes_per_day: extractDailyMinutes(userText),
    })
    return formatPlanForChat(plan)
  } catch {
    return generateRuleReply(userText)
  }
}

function getNickname(): string {
  try {
    const raw = localStorage.getItem(STORAGE_KEYS.userConfig)
    if (raw) {
      const config = JSON.parse(raw) as UserConfig
      return config.nickname || '旅人'
    }
  } catch { /* ignore */ }
  return '旅人'
}

export function useConversation() {
  const conversations = ref<Conversation[]>([])
  const messages = ref<Message[]>([])
  const currentId = ref<string | null>(null)
  const streaming = ref(false)
  const streamContent = ref('')

  const { execute: fetchConversations } = useAsync(
    async () => {
      conversations.value = await conversationApi.list()
      return conversations.value
    },
  )

  const { execute: fetchMessages } = useAsync(
    async (id: string) => {
      messages.value = await conversationApi.messages(id)
      currentId.value = id
      return messages.value
    },
  )

  const { execute: createConversation } = useAsync(
    async (title?: string) => {
      const conv = await conversationApi.create(title)
      currentId.value = conv.id
      await fetchConversations()
      return conv
    },
  )

  let streamAbort: AbortController | null = null
  /** 规则模式打字机的取消标志（同时用于组件卸载后终止循环） */
  let ruleCancelled = false

  onScopeDispose(() => {
    ruleCancelled = true
  })

  async function sendMessage(data: SendMessageRequest) {
    if (!currentId.value || streaming.value) return
    streaming.value = true
    streamContent.value = ''
    ruleCancelled = false
    const convId = currentId.value

    // 无论哪种模式，先本地插入用户消息：流式期间立即可见，且失败不丢用户输入
    const userMsg: Message = {
      id: 'local-user-' + Date.now(),
      conversation_id: convId,
      role: 'user',
      content: data.content,
      tokens: null,
      referenced_doc_ids: data.referenced_doc_ids ?? [],
      created_at: new Date().toISOString(),
    }
    messages.value = [...messages.value, userMsg]

    // 无API Key时使用本地降级回复（学习类意图会走领域规则引擎，见 buildLocalReply）
    if (!hasApiKey()) {
      const reply = await buildLocalReply(data.content)
      // 模拟打字机效果（可被 stopStreaming 或组件卸载中断）
      for (let i = 0; i <= reply.length; i += 3) {
        if (ruleCancelled) break
        streamContent.value = reply.slice(0, i)
        await new Promise(r => setTimeout(r, 15))
      }
      // 把规则回复加入本地列表
      const aiMsg: Message = {
        id: 'local-' + (Date.now() + 1),
        conversation_id: convId,
        role: 'assistant',
        content: ruleCancelled ? streamContent.value : reply,
        tokens: 0,
        referenced_doc_ids: [],
        created_at: new Date().toISOString(),
      }
      messages.value = [...messages.value, aiMsg]
      streaming.value = false
      streamContent.value = ''
      return
    }

    const controller = new AbortController()
    streamAbort = controller
    /** 后端在流内下发的业务错误（如会话不存在），流正常结束但无内容 */
    let streamError: string | null = null
    try {
      await conversationApi.sendStream(convId, data, (chunk) => {
        if (chunk.type === 'content' && chunk.content) {
          streamContent.value += chunk.content
        } else if (chunk.type === 'error') {
          streamError = (chunk as { error?: string }).error || '生成失败'
        }
      }, controller.signal)
      if (streamError) {
        toast.error('分身响应失败', streamError)
        return
      }
      await fetchMessages(convId)
    } catch (err) {
      if (!controller.signal.aborted) {
        const msg = err instanceof Error ? err.message : '发送失败'
        toast.error('分身响应失败', msg)
      }
      // 刷新失败时保留已流式生成的完整内容，避免回复凭空消失
      if (streamContent.value) {
        const fallbackMsg: Message = {
          id: 'local-fallback-' + Date.now(),
          conversation_id: convId,
          role: 'assistant',
          content: streamContent.value,
          tokens: null,
          referenced_doc_ids: [],
          created_at: new Date().toISOString(),
        }
        messages.value = [...messages.value, fallbackMsg]
      }
    } finally {
      streamContent.value = ''
      streaming.value = false
      streamAbort = null
    }
  }

  /** 中止当前流式生成 */
  function stopStreaming() {
    streamAbort?.abort()
    ruleCancelled = true
  }

  const { execute: summarize } = useAsync(
    async (documentId: string) => aiApi.summarize(documentId),
  )

  const { execute: suggestTags } = useAsync(
    async (documentId: string) => aiApi.suggestTags(documentId),
  )

  const { execute: getInspiration } = useAsync(
    async (documentId: string) => aiApi.inspiration(documentId),
  )

  async function deleteConversation(id: string) {
    await conversationApi.remove(id)
    conversations.value = conversations.value.filter((c) => c.id !== id)
    if (currentId.value === id) {
      currentId.value = null
      messages.value = []
    }
  }

  return {
    conversations,
    messages,
    currentId,
    streaming,
    streamContent,
    fetchConversations,
    fetchMessages,
    createConversation,
    sendMessage,
    stopStreaming,
    deleteConversation,
    summarize,
    suggestTags,
    getInspiration,
    hasApiKey,
  }
}
