import ajax from "../services/ajax"
import misago from "../index"

const PREVIEW_DEBOUNCE = 700

export class LivePreview {
  constructor(element) {
    this.element = element
    this.container = element.closest(".posting-split")
    this.body = element.querySelector("[misago-live-preview-body]")
    this.error = element.querySelector("[misago-live-preview-error]")
    this.textarea = this.container
      ? this.container.querySelector("textarea.markup-editor-textarea")
      : null
    this.attachments = this.container
      ? this.container.querySelector("[misago-editor-attachments-name]")
      : null

    this.timer = null
    this.sequence = 0
    this.lastMarkup = null

    this.handleInput = this.handleInput.bind(this)
  }

  get isValid() {
    return !!(this.container && this.textarea && this.body)
  }

  activate() {
    if (!this.isValid) return

    this.element.setAttribute("misago-live-preview-active", "true")

    // Server side preview is redundant once live preview is running
    this.container
      .querySelectorAll("[misago-live-preview-hide]")
      .forEach((element) => {
        element.hidden = true
      })

    this.textarea.addEventListener("input", this.handleInput)

    this.update()
  }

  handleInput() {
    window.clearTimeout(this.timer)
    this.timer = window.setTimeout(() => {
      this.update()
    }, PREVIEW_DEBOUNCE)
  }

  getAttachmentIds() {
    if (!this.attachments) return []

    const name = this.attachments.getAttribute("misago-editor-attachments-name")
    if (!name) return []

    const inputs = this.container.querySelectorAll(`input[name="${name}"]`)

    return [...inputs]
      .map((input) => parseInt(input.value, 10))
      .filter((id) => !isNaN(id))
  }

  update() {
    const markup = this.textarea.value
    if (markup === this.lastMarkup) return

    this.lastMarkup = markup

    const sequence = ++this.sequence

    this.element.setAttribute("misago-live-preview-loading", "true")

    ajax
      .post(misago.get("PREVIEW_MARKUP_API"), {
        post: markup,
        attachments: this.getAttachmentIds(),
      })
      .then((response) => {
        if (sequence !== this.sequence) return
        this.setPreview(response.html)
      })
      .catch((rejection) => {
        if (sequence !== this.sequence) return
        this.setError(
          rejection.detail ||
            rejection.statusText ||
            pgettext("live preview", "Unknown error has occurred.")
        )
      })
      .then(() => {
        if (sequence !== this.sequence) return
        this.element.removeAttribute("misago-live-preview-loading")
      })
  }

  setPreview(html) {
    this.body.innerHTML = html || ""
    if (this.error) this.error.hidden = true
  }

  setError(message) {
    if (!this.error) return
    this.error.textContent = message
    this.error.hidden = false
  }
}

export function activateLivePreviews() {
  if (!misago.get("PREVIEW_MARKUP_API")) return

  document
    .querySelectorAll(
      "[misago-live-preview]:not([misago-live-preview-active='true'])"
    )
    .forEach((element) => {
      new LivePreview(element).activate()
    })
}

export default LivePreview
