import QtQuick
import QtQuick.Controls

Window {
    id: root

    property bool activeSurface: false
    property bool selectionActive: false
    property real selectionX: 0
    property real selectionY: 0
    property real selectionWidth: 0
    property real selectionHeight: 0
    property real hintX: 24
    property real hintY: 24
    property bool showHint: false
    property bool showSize: false
    property real sizeX: 0
    property real sizeY: 0
    property string sizeLabel: ""

    signal pressedAt(real x, real y)
    signal movedAt(real x, real y)
    signal releasedAt(real x, real y)
    signal cancelRequested()

    Theme { id: theme }

    title: activeSurface ? "AI Translate · 圈选" : "AI Translate · 圈选 · 显示器"
    visible: false
    color: "transparent"
    flags: Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool

    function present() {
        root.show()
        root.raise()
        if (root.activeSurface) root.requestActivate()
    }

    Rectangle {
        visible: !root.selectionActive
        anchors.fill: parent
        color: theme.overlay
    }

    Item {
        visible: root.selectionActive
        anchors.fill: parent

        Rectangle {
            x: 0
            y: 0
            width: parent.width
            height: Math.max(0, root.selectionY)
            color: theme.overlay
        }
        Rectangle {
            x: 0
            y: root.selectionY
            width: Math.max(0, root.selectionX)
            height: Math.max(0, root.selectionHeight)
            color: theme.overlay
        }
        Rectangle {
            x: root.selectionX + root.selectionWidth
            y: root.selectionY
            width: Math.max(0, parent.width - x)
            height: Math.max(0, root.selectionHeight)
            color: theme.overlay
        }
        Rectangle {
            x: 0
            y: root.selectionY + root.selectionHeight
            width: parent.width
            height: Math.max(0, parent.height - y)
            color: theme.overlay
        }

        Rectangle {
            x: root.selectionX
            y: root.selectionY
            width: Math.max(0, root.selectionWidth)
            height: Math.max(0, root.selectionHeight)
            color: "transparent"
            border.color: theme.accent
            border.width: 2
        }

        Repeater {
            model: [
                [root.selectionX, root.selectionY],
                [root.selectionX + root.selectionWidth, root.selectionY],
                [root.selectionX, root.selectionY + root.selectionHeight],
                [root.selectionX + root.selectionWidth, root.selectionY + root.selectionHeight]
            ]

            delegate: Rectangle {
                required property var modelData
                width: 9
                height: 9
                x: modelData[0] - width / 2
                y: modelData[1] - height / 2
                color: theme.surface
                border.color: theme.accent
                border.width: 2
            }
        }
    }

    Rectangle {
        visible: root.showHint
        x: root.hintX
        y: root.hintY
        width: 258
        height: 72
        radius: 8
        color: "#E60F1724"
        border.color: "#3DFFFFFF"
        border.width: 1

        Column {
            anchors.centerIn: parent
            spacing: 5

            Label {
                anchors.horizontalCenter: parent.horizontalCenter
                text: "拖动选择要识别的区域"
                color: "#FFFFFF"
                font.family: theme.fontFamily
                font.pixelSize: 15
                font.weight: Font.DemiBold
            }
            Label {
                anchors.horizontalCenter: parent.horizontalCenter
                text: "Esc 取消"
                color: "#CBD5E1"
                font.family: theme.fontFamily
                font.pixelSize: 12
            }
        }
    }

    Rectangle {
        visible: root.showSize
        x: root.sizeX
        y: root.sizeY
        width: sizeText.implicitWidth + 22
        height: 34
        radius: 7
        color: "#E60F1724"
        border.color: "#3DFFFFFF"
        border.width: 1

        Label {
            id: sizeText
            anchors.centerIn: parent
            text: root.sizeLabel
            color: "#FFFFFF"
            font.family: theme.fontFamily
            font.pixelSize: 12
            font.weight: Font.DemiBold
        }
    }

    MouseArea {
        anchors.fill: parent
        cursorShape: Qt.CrossCursor
        acceptedButtons: Qt.LeftButton
        onPressed: function(mouse) { root.pressedAt(mouse.x, mouse.y) }
        onPositionChanged: function(mouse) {
            if (pressed) root.movedAt(mouse.x, mouse.y)
        }
        onReleased: function(mouse) { root.releasedAt(mouse.x, mouse.y) }
    }

    Shortcut {
        sequence: "Escape"
        context: Qt.ApplicationShortcut
        onActivated: root.cancelRequested()
    }
}
