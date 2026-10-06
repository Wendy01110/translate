import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

ApplicationWindow {
    id: window
    width: 800
    height: 560
    minimumWidth: 640
    minimumHeight: 400
    visible: false
    title: "翻译历史"
    color: theme.windowBackground

    property bool savingEnabled: false
    property var entryLabels: []
    property int selectedIndex: -1
    property string sourceText: ""
    property string translatedText: ""
    property string statusText: ""
    property bool canReuse: false
    property bool canClear: false
    signal savingToggled(bool enabled)
    signal entrySelected(int index)
    signal reuseRequested()
    signal clearRequested()

    Theme { id: theme }

    function present() {
        show()
        raise()
        requestActivate()
    }

    onClosing: function(close) {
        close.accepted = false
        hide()
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 24
        spacing: 16

        CheckBox {
            text: "保留翻译历史（仅本机）"
            checked: window.savingEnabled
            font.family: theme.fontFamily
            font.pixelSize: 14
            onToggled: window.savingToggled(checked)
        }

        AppComboBox {
            Layout.fillWidth: true
            model: window.entryLabels.length > 0 ? window.entryLabels : ["暂无历史记录"]
            currentIndex: Math.max(0, window.selectedIndex)
            enabled: window.entryLabels.length > 0
            onActivated: window.entrySelected(index)
        }

        RowLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            spacing: 16

            Repeater {
                model: ["原文", "译文"]
                delegate: ColumnLayout {
                    required property string modelData
                    required property int index
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    Layout.preferredWidth: 1
                    spacing: 8

                    Label {
                        text: modelData
                        font.family: theme.fontFamily
                        font.pixelSize: 14
                        color: theme.textPrimary
                    }

                    AppTextArea {
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        readOnly: true
                        text: index === 0 ? window.sourceText : window.translatedText
                    }
                }
            }
        }

        Label {
            Layout.fillWidth: true
            text: window.statusText
            wrapMode: Text.WordWrap
            font.family: theme.fontFamily
            font.pixelSize: 12
            color: theme.textSecondary
        }

        RowLayout {
            Layout.fillWidth: true
            AppButton {
                text: "清空历史…"
                enabled: window.canClear
                onClicked: clearDialog.open()
            }
            Item { Layout.fillWidth: true }
            AppButton {
                text: "放回翻译窗口"
                kind: "primary"
                enabled: window.canReuse
                onClicked: window.reuseRequested()
            }
        }
    }

    Dialog {
        id: clearDialog
        anchors.centerIn: parent
        title: "清空全部翻译历史？"
        modal: true
        standardButtons: Dialog.Ok | Dialog.Cancel
        Label { text: "清空后无法恢复，当前翻译窗口的内容会保留。" }
        onAccepted: window.clearRequested()
    }
}
