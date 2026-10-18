pragma ComponentBehavior: Bound
import Spectra
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Dialogs

Pane {
    id: workspace
    required property Controller controller
    readonly property var options: workspace.controller.settings
    signal quitRequested
    padding: 16

    ColumnLayout {
        anchors.fill: parent
        spacing: 12
        Label {
            text: qsTr("Spectra")
            font.pointSize: 21
            font.weight: Font.Medium
        }
        Label {
            text: qsTr("Arrange media by visual similarity, then preview or apply new filenames.")
        }
        SplitView {
            Layout.fillWidth: true
            Layout.fillHeight: true
            orientation: workspace.width < 1050 ? Qt.Vertical : Qt.Horizontal
            ColumnLayout {
                SplitView.preferredWidth: 760
                SplitView.preferredHeight: 480
                SplitView.minimumWidth: 400
                TabBar {
                    id: tabs
                    Layout.fillWidth: true
                    TabButton {
                        text: qsTr("Sort && Rename")
                    }
                    TabButton {
                        text: qsTr("Settings")
                    }
                    TabButton {
                        text: qsTr("Extras")
                    }
                }
                StackLayout {
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    currentIndex: tabs.currentIndex
                    SortPanel {
                        controller: workspace.controller
                        onBrowseRequested: folderPicker.open()
                    }
                    SettingsPanel {
                        controller: workspace.controller
                    }
                    ExtrasPanel {
                        controller: workspace.controller
                    }
                }
            }
            LogPanel {
                controller: workspace.controller
                SplitView.fillWidth: true
                SplitView.minimumWidth: 300
                SplitView.minimumHeight: 130
            }
        }
        RunBar {
            Layout.fillWidth: true
            controller: workspace.controller
            onStartRequested: {
                if (workspace.options["dry_run"])
                    workspace.controller.start();
                else
                    renameConfirmation.open();
            }
        }
        ProgressPanel {
            Layout.fillWidth: true
            controller: workspace.controller
        }
    }

    FolderDialog {
        id: folderPicker
        title: qsTr("Select Media Folder")
        onAccepted: workspace.controller.selectFolder(selectedFolder)
    }
    MessageDialog {
        id: renameConfirmation
        title: qsTr("Confirm Rename")
        text: workspace.options["backup"] ? qsTr("Rename supported media in this folder? A backup will be created.") : qsTr("Rename supported media in this folder? No backup will be created.")
        buttons: MessageDialog.Yes | MessageDialog.No
        onButtonClicked: button => {
            if (button === MessageDialog.Yes)
                workspace.controller.start();
        }
    }
    MessageDialog {
        id: updateConfirmation
        title: qsTr("Update Available")
        buttons: MessageDialog.Yes | MessageDialog.No
        onButtonClicked: button => {
            if (button === MessageDialog.Yes)
                workspace.controller.downloadUpdate();
        }
    }
    Loader {
        id: completionLoader
        active: false
        property bool dryRun: true
        sourceComponent: CompletionDialog {
            controller: workspace.controller
            dryRun: completionLoader.dryRun
            onClosed: completionLoader.active = false
            onQuitRequested: workspace.quitRequested()
            Component.onCompleted: open()
        }
    }
    Connections {
        target: workspace.controller
        function onCompleted(dryRun) {
            completionLoader.dryRun = dryRun;
            completionLoader.active = true;
        }
        function onUpdateAvailable(version) {
            updateConfirmation.text = qsTr("Spectra %1 is available. Download and open Setup?").arg(version);
            updateConfirmation.open();
        }
    }
}
