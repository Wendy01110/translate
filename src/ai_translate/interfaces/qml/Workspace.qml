import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

ApplicationWindow {
    id: root

    property alias sourceText: sourceArea.text
    property alias translationText: translationArea.text
    property string footnote: "等待输入"
    property bool sourceEditable: true
    property bool busy: false
    property bool pinned: false
    property bool translateAvailable: false
    property bool copyFeedback: false
    property var targetLabels: []
    property int targetIndex: 0

    signal translateRequested(string text)
    signal targetLanguageSelected(int index)
    signal pinRequested()
    signal copyRequested()

    Theme { id: theme }

    title: "AI Translate · 翻译"
    width: 800
    height: 560
    minimumWidth: 680
    minimumHeight: 480
    visible: false
    color: theme.windowBackground

    function present(focusSource) {
        root.show()
        root.raise()
        root.requestActivate()
        if (focusSource) {
            Qt.callLater(function() { sourceArea.forceEditorFocus() })
        }
    }

    onClosing: function(close) {
        close.accepted = false
        root.hide()
    }

    Shortcut {
        sequence: "Ctrl+Return"
        context: Qt.ApplicationShortcut
        enabled: translateButton.enabled
        onActivated: root.translateRequested(sourceArea.text)
    }

    Shortcut {
        sequence: "Ctrl+Enter"
        context: Qt.ApplicationShortcut
        enabled: translateButton.enabled
        onActivated: root.translateRequested(sourceArea.text)
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.leftMargin: 24
        anchors.rightMargin: 24
        anchors.topMargin: 22
        anchors.bottomMargin: 18
        spacing: 16

        RowLayout {
            Layout.fillWidth: true
            spacing: 10

            Label {
                text: "目标语言"
                color: theme.textPrimary
                font.family: theme.fontFamily
                font.pixelSize: 14
                font.weight: Font.DemiBold
            }

            AppComboBox {
                id: targetCombo
                objectName: "targetLanguageCombo"
                Layout.preferredWidth: 136
                Layout.preferredHeight: 40
                model: root.targetLabels
                currentIndex: root.targetIndex
                enabled: !root.busy && root.targetLabels.length > 0
                font.family: theme.fontFamily
                font.pixelSize: 14
                onActivated: function(index) {
                    root.targetIndex = index
                    root.targetLanguageSelected(index)
                }
            }

            Item { Layout.fillWidth: true }

            AppButton {
                id: translateButton
                objectName: "translateButton"
                text: root.busy ? "翻译中…" : "翻译"
                kind: "primary"
                iconSource: "icons/translate.svg"
                enabled: root.sourceEditable && root.translateAvailable && !root.busy
                onClicked: root.translateRequested(sourceArea.text)
            }

            AppButton {
                objectName: "pinButton"
                text: root.pinned ? "取消置顶" : "置顶"
                iconSource: "icons/pin.svg"
                enabled: !root.busy
                onClicked: root.pinRequested()
            }

            AppButton {
                objectName: "copyButton"
                text: root.copyFeedback ? "已复制" : "复制译文"
                iconSource: "icons/copy.svg"
                enabled: translationArea.text.length > 0 && !root.busy
                onClicked: root.copyRequested()
            }
        }

        GridLayout {
            id: editors
            Layout.fillWidth: true
            Layout.fillHeight: true
            columns: width >= 700 ? 2 : 1
            rowSpacing: 14
            columnSpacing: 18

            ColumnLayout {
                Layout.fillWidth: true
                Layout.fillHeight: true
                Layout.minimumHeight: 150
                spacing: 8

                Label {
                    text: "原文"
                    color: theme.textPrimary
                    font.family: theme.fontFamily
                    font.pixelSize: 17
                    font.weight: Font.DemiBold
                }

                AppTextArea {
                    id: sourceArea
                    objectName: "sourceArea"
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    readOnly: !root.sourceEditable || root.busy
                    emphasized: false
                    placeholderText: "输入文字，或使用划词与截图热键开始"
                }
            }

            ColumnLayout {
                Layout.fillWidth: true
                Layout.fillHeight: true
                Layout.minimumHeight: 150
                spacing: 8

                Label {
                    text: "译文"
                    color: theme.textPrimary
                    font.family: theme.fontFamily
                    font.pixelSize: 17
                    font.weight: Font.DemiBold
                }

                AppTextArea {
                    id: translationArea
                    objectName: "translationArea"
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    readOnly: true
                    emphasized: true
                }
            }
        }

        Rectangle {
            Layout.fillWidth: true
            implicitHeight: 1
            color: theme.border
        }

        RowLayout {
            Layout.fillWidth: true
            spacing: 12

            Rectangle {
                width: 7
                height: 7
                radius: 3.5
                color: root.busy ? theme.accent : theme.textTertiary

                SequentialAnimation on opacity {
                    running: root.busy
                    loops: Animation.Infinite
                    NumberAnimation { from: 0.35; to: 1; duration: 650 }
                    NumberAnimation { from: 1; to: 0.35; duration: 650 }
                }
            }

            Label {
                Layout.fillWidth: true
                text: root.footnote.length > 0 ? root.footnote : "等待输入"
                color: theme.textSecondary
                elide: Text.ElideRight
                font.family: theme.fontFamily
                font.pixelSize: 12
            }

            Label {
                text: "Ctrl+Enter 翻译"
                color: theme.textSecondary
                font.family: theme.fontFamily
                font.pixelSize: 12
            }
        }
    }
}
