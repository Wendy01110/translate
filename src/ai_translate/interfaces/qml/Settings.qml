import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

ApplicationWindow {
    id: root

    property bool busy: false
    property string statusText: ""
    property bool statusSuccess: false
    property int currentSection: 0

    property var translateProviderOptions: []
    property var translateModelOptions: []
    property var ocrEngineOptions: []
    property var localTierOptions: []
    property var ocrModelOptions: []
    property var imageModeOptions: []
    property var sourceLanguageOptions: []
    property var targetLanguageOptions: []

    property string translateProvider: ""
    property string translateBaseUrl: ""
    property string translateApiKey: ""
    property string translateModel: ""
    property string translateRegion: ""
    property string ocrEngine: ""
    property string localTier: ""
    property string ocrStandardApiKey: ""
    property string ocrBaseUrl: ""
    property string ocrApiKey: ""
    property string ocrModel: ""
    property string ocrMinConfidence: ""
    property string imageMode: ""
    property string sourceLanguage: ""
    property string targetLanguage: ""
    property string selectionHotkey: ""
    property string ocrHotkey: ""
    property string liveHotkey: ""

    signal commitRequested(bool closeAfterSave)

    Theme { id: theme }

    title: "AI Translate 设置"
    width: 780
    height: 680
    minimumWidth: 700
    minimumHeight: 560
    visible: false
    color: theme.windowBackground

    function selectedIndex(options, value) {
        if (!options || options.length === 0) return -1
        const index = options.indexOf(value)
        return index >= 0 ? index : 0
    }

    function present() {
        root.show()
        root.raise()
        root.requestActivate()
    }

    onClosing: function(close) {
        close.accepted = false
        root.hide()
    }

    component FieldLabel: Label {
        Layout.preferredWidth: 154
        Layout.alignment: Qt.AlignVCenter
        color: theme.textPrimary
        font.family: theme.fontFamily
        font.pixelSize: 14
    }

    component SectionTitle: Label {
        Layout.columnSpan: 2
        Layout.fillWidth: true
        color: theme.textPrimary
        font.family: theme.fontFamily
        font.pixelSize: 16
        font.weight: Font.DemiBold
        bottomPadding: 5
    }

    RowLayout {
        anchors.fill: parent
        spacing: 0

        Rectangle {
            Layout.preferredWidth: 226
            Layout.fillHeight: true
            color: "#FBFCFE"
            border.color: theme.border
            border.width: 0

            Rectangle {
                width: 1
                color: theme.border
                anchors.top: parent.top
                anchors.bottom: parent.bottom
                anchors.right: parent.right
            }

            ColumnLayout {
                anchors.fill: parent
                anchors.leftMargin: 22
                anchors.rightMargin: 22
                anchors.topMargin: 28
                anchors.bottomMargin: 22
                spacing: 8

                Label {
                    text: "设置"
                    color: theme.textPrimary
                    font.family: theme.fontFamily
                    font.pixelSize: 25
                    font.weight: Font.DemiBold
                }

                Label {
                    Layout.fillWidth: true
                    text: "翻译与 OCR 独立配置；应用后立即重建当前运行时。"
                    color: theme.textSecondary
                    wrapMode: Text.WordWrap
                    font.family: theme.fontFamily
                    font.pixelSize: 12
                    lineHeight: 1.35
                    lineHeightMode: Text.ProportionalHeight
                }

                Item { Layout.preferredHeight: 22 }

                Repeater {
                    model: ["翻译", "OCR", "语言与热键"]

                    delegate: NavButton {
                        required property int index
                        required property string modelData
                        objectName: "settingsNav" + index
                        Layout.fillWidth: true
                        text: modelData
                        selected: root.currentSection === index
                        onClicked: root.currentSection = index
                    }
                }

                Item { Layout.fillHeight: true }

                Label {
                    Layout.fillWidth: true
                    text: "密钥字段始终遮挡显示"
                    color: theme.textTertiary
                    font.family: theme.fontFamily
                    font.pixelSize: 11
                    wrapMode: Text.WordWrap
                }
            }
        }

        Rectangle {
            Layout.fillWidth: true
            Layout.fillHeight: true
            color: theme.windowBackground

            ColumnLayout {
                anchors.fill: parent
                anchors.leftMargin: 36
                anchors.rightMargin: 36
                anchors.topMargin: 28
                anchors.bottomMargin: 24
                spacing: 14

                Label {
                    text: ["翻译", "OCR", "语言与热键"][root.currentSection]
                    color: theme.textPrimary
                    font.family: theme.fontFamily
                    font.pixelSize: 24
                    font.weight: Font.DemiBold
                }

                StackLayout {
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    currentIndex: root.currentSection

                    ScrollView {
                        id: translateScroll
                        clip: true
                        ScrollBar.horizontal.policy: ScrollBar.AlwaysOff

                        GridLayout {
                            width: translateScroll.availableWidth
                            columns: 2
                            columnSpacing: 18
                            rowSpacing: 12

                            SectionTitle { text: "翻译来源" }

                            FieldLabel { text: "翻译来源" }
                            AppComboBox {
                                Layout.fillWidth: true
                                model: root.translateProviderOptions
                                currentIndex: root.selectedIndex(root.translateProviderOptions, root.translateProvider)
                                onActivated: root.translateProvider = currentText
                            }

                            FieldLabel { text: "API 地址" }
                            AppField {
                                Layout.fillWidth: true
                                text: root.translateBaseUrl
                                onTextEdited: root.translateBaseUrl = text
                            }

                            FieldLabel { text: "API 密钥" }
                            AppField {
                                Layout.fillWidth: true
                                secret: true
                                text: root.translateApiKey
                                onTextEdited: root.translateApiKey = text
                            }

                            FieldLabel { text: "模型" }
                            AppComboBox {
                                Layout.fillWidth: true
                                editable: true
                                model: root.translateModelOptions
                                editText: root.translateModel
                                onEditTextChanged: if (activeFocus) root.translateModel = editText
                                onActivated: root.translateModel = currentText
                            }

                            FieldLabel { text: "Microsoft 区域" }
                            AppField {
                                Layout.fillWidth: true
                                text: root.translateRegion
                                onTextEdited: root.translateRegion = text
                            }

                            Label {
                                Layout.columnSpan: 2
                                Layout.fillWidth: true
                                text: "内置 Google / Bing / DeepL 不读取 API 地址、密钥和模型；其它来源按需填写并保持独立。"
                                color: theme.textSecondary
                                wrapMode: Text.WordWrap
                                font.family: theme.fontFamily
                                font.pixelSize: 12
                                topPadding: 8
                            }
                        }
                    }

                    ScrollView {
                        id: ocrScroll
                        clip: true
                        ScrollBar.horizontal.policy: ScrollBar.AlwaysOff

                        GridLayout {
                            width: ocrScroll.availableWidth
                            columns: 2
                            columnSpacing: 18
                            rowSpacing: 12

                            SectionTitle { text: "OCR 分流" }

                            FieldLabel { text: "OCR 方法" }
                            AppComboBox {
                                Layout.fillWidth: true
                                model: root.ocrEngineOptions
                                currentIndex: root.selectedIndex(root.ocrEngineOptions, root.ocrEngine)
                                onActivated: root.ocrEngine = currentText
                            }

                            FieldLabel { text: "本地 Paddle 档位" }
                            AppComboBox {
                                Layout.fillWidth: true
                                model: root.localTierOptions
                                currentIndex: root.selectedIndex(root.localTierOptions, root.localTier)
                                onActivated: root.localTier = currentText
                            }

                            FieldLabel { text: "普通 OCR 密钥" }
                            AppField {
                                Layout.fillWidth: true
                                secret: true
                                text: root.ocrStandardApiKey
                                onTextEdited: root.ocrStandardApiKey = text
                            }

                            FieldLabel { text: "高级 API 地址" }
                            AppField {
                                Layout.fillWidth: true
                                text: root.ocrBaseUrl
                                onTextEdited: root.ocrBaseUrl = text
                            }

                            FieldLabel { text: "高级 API 密钥" }
                            AppField {
                                Layout.fillWidth: true
                                secret: true
                                text: root.ocrApiKey
                                onTextEdited: root.ocrApiKey = text
                            }

                            FieldLabel { text: "高级模型" }
                            AppComboBox {
                                Layout.fillWidth: true
                                editable: true
                                model: root.ocrModelOptions
                                editText: root.ocrModel
                                onEditTextChanged: if (activeFocus) root.ocrModel = editText
                                onActivated: root.ocrModel = currentText
                            }

                            FieldLabel { text: "本机置信度" }
                            AppField {
                                Layout.fillWidth: true
                                text: root.ocrMinConfidence
                                onTextEdited: root.ocrMinConfidence = text
                            }

                            FieldLabel { text: "切图模式" }
                            AppComboBox {
                                Layout.fillWidth: true
                                model: root.imageModeOptions
                                currentIndex: root.selectedIndex(root.imageModeOptions, root.imageMode)
                                onActivated: root.imageMode = currentText
                            }

                            Label {
                                Layout.columnSpan: 2
                                Layout.fillWidth: true
                                text: "Windows 没有本地普通 OCR；安装 PaddleOCR 后，自动模式会先用本地高级，再进入 API 两层。"
                                color: theme.textSecondary
                                wrapMode: Text.WordWrap
                                font.family: theme.fontFamily
                                font.pixelSize: 12
                                topPadding: 8
                            }
                        }
                    }

                    ScrollView {
                        id: languageScroll
                        clip: true
                        ScrollBar.horizontal.policy: ScrollBar.AlwaysOff

                        GridLayout {
                            width: languageScroll.availableWidth
                            columns: 2
                            columnSpacing: 18
                            rowSpacing: 12

                            SectionTitle { text: "语言与快捷操作" }

                            FieldLabel { text: "源语言" }
                            AppComboBox {
                                Layout.fillWidth: true
                                model: root.sourceLanguageOptions
                                currentIndex: root.selectedIndex(root.sourceLanguageOptions, root.sourceLanguage)
                                onActivated: root.sourceLanguage = currentText
                            }

                            FieldLabel { text: "目标语言" }
                            AppComboBox {
                                Layout.fillWidth: true
                                model: root.targetLanguageOptions
                                currentIndex: root.selectedIndex(root.targetLanguageOptions, root.targetLanguage)
                                onActivated: root.targetLanguage = currentText
                            }

                            FieldLabel { text: "划词热键" }
                            AppField {
                                Layout.fillWidth: true
                                text: root.selectionHotkey
                                onTextEdited: root.selectionHotkey = text
                            }

                            FieldLabel { text: "截图热键" }
                            AppField {
                                Layout.fillWidth: true
                                text: root.ocrHotkey
                                onTextEdited: root.ocrHotkey = text
                            }

                            FieldLabel { text: "实时热键" }
                            AppField {
                                Layout.fillWidth: true
                                text: root.liveHotkey
                                onTextEdited: root.liveHotkey = text
                            }

                            Label {
                                Layout.columnSpan: 2
                                Layout.fillWidth: true
                                text: "格式示例：alt+e、ctrl+alt+w。三组热键不能相同。"
                                color: theme.textSecondary
                                wrapMode: Text.WordWrap
                                font.family: theme.fontFamily
                                font.pixelSize: 12
                                topPadding: 8
                            }
                        }
                    }
                }

                Label {
                    Layout.fillWidth: true
                    text: root.statusText
                    visible: text.length > 0
                    color: root.statusSuccess ? theme.success : theme.danger
                    font.family: theme.fontFamily
                    font.pixelSize: 12
                    wrapMode: Text.WordWrap
                }

                Rectangle {
                    Layout.fillWidth: true
                    implicitHeight: 1
                    color: theme.border
                }

                RowLayout {
                    Layout.fillWidth: true
                    spacing: 10

                    Item { Layout.fillWidth: true }

                    AppButton {
                        objectName: "applyButton"
                        text: "应用"
                        enabled: !root.busy
                        onClicked: root.commitRequested(false)
                    }

                    AppButton {
                        objectName: "saveButton"
                        text: root.busy ? "保存中…" : "保存"
                        kind: "primary"
                        enabled: !root.busy
                        onClicked: root.commitRequested(true)
                    }
                }
            }
        }
    }
}
