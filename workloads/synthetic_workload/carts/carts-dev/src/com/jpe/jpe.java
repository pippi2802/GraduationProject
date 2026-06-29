/* This program is free software; you can redistribute it and/or
 * modify it under the terms of the GNU General Public License
 * as published by the Free Software Foundation; either version 2
 * of the License, or any later version.
 *
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License
 * along with this program; if not, write to the Free Software
 * Foundation, Inc., 59 Temple Place - Suite 330, Boston, MA  02111-1307, USA.
 */

//jpe.java - the main class of the JPE application
//(C)2000-2003 Mark Beynon
//mark@jpedit.co.uk
//http://www.jpedit.co.uk
//last edited 31 October 2003
package com.jpe;

import java.awt.Font;
import java.awt.Color;
import java.awt.FlowLayout;
import java.awt.BorderLayout;
import java.awt.Cursor;
import java.awt.Frame;
import java.awt.Toolkit;

import java.awt.event.KeyListener;
import java.awt.event.WindowStateListener;
import java.awt.event.WindowListener;
import java.awt.event.ActionListener;
import java.awt.event.ComponentListener;
import java.awt.event.ComponentEvent;
import java.awt.event.MouseListener;
import java.awt.event.MouseAdapter;
import java.awt.event.FocusListener;
import java.awt.event.WindowEvent;
import java.awt.event.ActionEvent;
import java.awt.event.MouseEvent;
import java.awt.event.FocusEvent;
import java.awt.event.KeyEvent;
import java.awt.event.InputEvent;
import javax.swing.event.ChangeListener;
import javax.swing.event.ChangeEvent;

import javax.swing.event.DocumentEvent;
import javax.swing.event.UndoableEditListener;
import javax.swing.event.UndoableEditEvent;
import javax.swing.event.CaretListener;
import javax.swing.event.CaretEvent;
import javax.swing.filechooser.FileFilter;

import javax.swing.UIManager;
import javax.swing.JFrame;
import javax.swing.border.EtchedBorder;
import javax.swing.ImageIcon;
import javax.swing.JMenu;
import javax.swing.KeyStroke;
import javax.swing.JToolBar;
import javax.swing.Box;
import javax.swing.BoxLayout;
import javax.swing.JLabel;
import javax.swing.JToggleButton;
import javax.swing.JButton;
import javax.swing.JPanel;
import javax.swing.JOptionPane;
import javax.swing.JMenuItem;
import javax.swing.JPopupMenu;
import javax.swing.JMenuBar;
import java.util.Properties;
import java.sql.Time;

import java.io.File;
import java.io.FileNotFoundException;
import java.io.IOException;
import java.io.FileInputStream;
import java.io.FileOutputStream;

import javax.swing.undo.UndoManager;
import com.io.*;
import com.misc.*;
import com.utils.*;
import com.actions.*;
import com.syntax.*;
import edu.penn.rtg.schedulingapp.util.CartsFileChooser;
/**
 * Main class of the tool. This contains the Menu items, Buttons and also the
 * tabbed pane of the scheduling systems. The class also contains the handlers
 * for all the actions associated with menu items and buttons.
 */
public class jpe extends JFrame implements ActionListener, MouseListener,
		UndoableEditListener, ChangeListener, FocusListener, KeyListener,
		Constants, WindowStateListener, ComponentListener, WindowListener {

	/**
	 * Array of the systems of the tool. Each system is represented by a
	 * ComponentArea object
	 */
	private ComponentArea Editors[] = new ComponentArea[99]; //meng: 99 is the max number of systems/tabs carts can support 
	private ComponentArea sampleEditor = new ComponentArea();

	/**
	 * Array to keep track of the details of the file which have been opened in
	 * the tool. The details include file name, file modification flag.
	 */
	private long fileModified[] = new long[99];
	private boolean dirty[] = new boolean[99];
	private boolean readOnly[] = new boolean[99];
	private String fileNames[] = new String[99];
	private File currFileTypes[] = new File[99];
	private int currentCursorPos[] = new int[99];
	private String syntaxType[] = new String[99];
	protected UndoManager undo[] = new UndoManager[99];

	private boolean checkfilemod = false;
	private boolean readonlynotify = false;

	private int UndoLimit = 50;
	private int EditCount = 0;
	private int untitled = 1;
	private int tabplacement = 1;

	/**
	 * Tabbed pane for scheduling systems. Each tab will contain 'ComponentArea'
	 * object.
	 */
	private CloseTabbedPane componentTabbedPane;

	/**
	 * Toolbar of buttons
	 */
	private JToolBar jpButtons;

	/**
	 * Member objects for items in the File Menu
	 */
	private JMenuItem jmiNew, jmiOpen, jmiSave, jmiSaveAs, jmiSaveAll,
			jmiClose, jmiCloseAll, jmiPrint, jmiQuit;

	/**
	 * Member objects for items in the Edit Menu
	 */
	private JMenuItem jmiCut, jmiCopy, jmiPaste, jmiPopCut, jmiPopCopy,
			jmiPopPaste, jmiSelectAll, jmiUndo, jmiUndoAll, jmiRedo,
			jmiRedoAll, jmiPopRedo, jmiPopUndo;

	/**
	 * Member objects for items in the About Menu
	 */
	private JMenuItem jmiAbout;

	/**
	 * Member objects for items in the Search Menu
	 */
	private JMenuItem jmiSearch, jmiSearchNext, jmiReplace;

	/**
	 * Member objects for items in the Component/Task Menu
	 */
	private JMenuItem jmiAddComponent, jmiAddTask, jmiRemoveComponent,
			jmiRemoveTask, jmiEditComponent, jmiEditTask;

	/**
	 * Member objects for items in the Algorithms Menu
	 */
	//xm
	private JMenuItem jmiAlgoPeriodic, jmiAlgoEDP, jmiAlgoDMPR, jmiAlgoMPR,jmiAlgoEQV, 
				jmiAlgoCADMPR_TASKCENTRIC, jmiAlgoCADMPR_MODELCENTRIC, jmiAlgoCADMPR_HYBRID;

	/**
	 * Member objects for the buttons present in the tool
	 */
	private JButton jbtOpen, jbtSave, jbtSaveAs, jbtNew, jbtCut, jbtCopy,
			jbtPaste, jbtPrint, jbtRedo, jbtUndo, jbtSaveAll,
			jbtConvertForward, jbtConvertBackward;

	private JLabel jpeStatusBar;
	private JPanel JToolMain, JtoolBar;
	private JPanel statusPanel;
	private String dir = System.getProperty("user.dir");
	private JPopupMenu jpopupmenu = new JPopupMenu();

	/**
	 * Menus going to be added to the Frame
	 */
	private JMenu fileMenu, editMenu, searchMenu, componentMenu, algoMenu,
			helpMenu;

	private Properties p;
	private JButton jbtSearch, jbtReplace;
	private int gutwidth, tabs;
	private int gutint;

	private Color textHighlightColor = new Color(0xccccff);
	private Color caretColor = Color.blue;
	private Color bracketColor = Color.red;
	private Color highlightColor = new Color(0xe0e0e0);
	private Color gutterFor = new Color(170, 170, 170);
	private Color gutterBak = Color.white;
	private Color gutterHigh = new Color(71, 71, 71);

	private int appWidth = 800;
	private int appHeight = 600;

	// JW added
	private boolean bConvertTree=true;

	static jpe singleInstance;

	/**
	 * Main class for JPE. Creates an object for the static reference present in
	 * the class
	 * 
	 * @param args
	 *            Command line arguments
	 */
	public static void main(String[] args) {
		singleInstance = new jpe();
		Utils.setParent(singleInstance);
		singleInstance.setExtendedState(Frame.MAXIMIZED_BOTH);
		singleInstance.addComponentListener(singleInstance);
		Utils.centerComponent(singleInstance);
		singleInstance.setVisible(true);
		singleInstance.setDefaultCloseOperation(DO_NOTHING_ON_CLOSE);
		singleInstance.setFont(SYSTEM_FONT);
	}

	/**
	 * Constructor for JPE. It initializes all the GUI components of the tool.
	 */
	public jpe() {
		super();
		this.addWindowListener(new WindowHandler(this));
		setTitle("Compositional Analysis of Real-Time Systems");
		setIconImage(new ImageIcon("images/r_icon.gif").getImage());
		try {
			UIManager.setLookAndFeel(UIManager
					.getCrossPlatformLookAndFeelClassName());
		} catch (Exception exc) {
			System.out.println("Error loading L&F: " + exc);
		}

		// Initializing the Menus
		fileMenu = MenuFactory.createMenu("File", 0, 'F', null, this);
		editMenu = MenuFactory.createMenu("Edit", 0, 'E', null, this);
		searchMenu = MenuFactory.createMenu("Search", 0, 'S', null, this);
		componentMenu = MenuFactory.createMenu("Component/Task", 0, 'C', null,
				this);
		algoMenu = MenuFactory.createMenu("Compute-Interface", 0, 'I', null,
				this);
		helpMenu = MenuFactory.createMenu("About", 0, 0, null, this);

		JMenuBar jmb = new JMenuBar();
		setJMenuBar(jmb);
		jmb.add(fileMenu);
		jmb.add(editMenu);
		jmb.add(searchMenu);
		jmb.add(componentMenu);
		jmb.add(algoMenu);
		jmb.add(helpMenu);
		fileMenu.add(jmiNew = MenuFactory.createMenuItem("New System", null,
				New, 'O', 0, this));
		fileMenu.add(jmiOpen = MenuFactory.createMenuItem("Open..", null, null,
				'O', 0, this));
		fileMenu.addSeparator();
		fileMenu.add(jmiSave = MenuFactory.createMenuItem("Save", null, null,
				'S', 0, this));
		fileMenu.add(jmiSaveAs = MenuFactory.createMenuItem("Save As..", null,
				null, 0, 0, this));
		fileMenu.add(jmiSaveAll = MenuFactory.createMenuItem("Save All..",
				null, null, 0, 0, this));
		fileMenu.addSeparator();
		fileMenu.add(jmiPrint = MenuFactory.createMenuItem("Print", null,
				null, 0, 0, this));
		fileMenu.addSeparator();
		fileMenu.add(jmiClose = MenuFactory.createMenuItem("Close", null,
				null, 'W', 0, this));
		fileMenu.addSeparator();
		fileMenu.add(jmiCloseAll = MenuFactory.createMenuItem("Close All",
				null, null, 0, 0, this));
		fileMenu.addSeparator();
		fileMenu.add(jmiQuit = MenuFactory.createMenuItem("Quit", null, null,
				'Q', 0, this));

		editMenu.add(jmiUndo = MenuFactory.createMenuItem("Undo", null, null,
				'Z', 0, this));
		editMenu.add(jmiUndoAll = MenuFactory.createMenuItem("Undo All", null,
				null, 0, 0, this));
		editMenu.add(jmiRedo = MenuFactory.createMenuItem("Redo", null, null,
				'Y', 0, this));
		editMenu.add(jmiRedoAll = MenuFactory.createMenuItem("Redo All", null,
				null, 0, 0, this));
		editMenu.addSeparator();
		editMenu.add(jmiCut = MenuFactory.createMenuItem("Cut", null, null, 0,
				0, this));
		editMenu.add(jmiCopy = MenuFactory.createMenuItem("Copy", null, null,
				0, 0, this));
		editMenu.add(jmiPaste = MenuFactory.createMenuItem("Paste", null,
				null, 0, 0, this));
		editMenu.addSeparator();
		editMenu.add(jmiSelectAll = MenuFactory.createMenuItem("Select All",
				null, null, 'A', 0, this));

		// add items to search menu
		searchMenu.add(jmiSearch = MenuFactory.createMenuItem("Find", null,
				null, 0, 0, this));
		searchMenu.add(jmiSearchNext = MenuFactory.createMenuItem("Find Next",
				null, null, 0, 0, this));
		searchMenu.addSeparator();
		searchMenu.add(jmiReplace = MenuFactory.createMenuItem("Replace", null,
				null, 0, 0, this));
		jmiSearch.setAccelerator(KeyStroke.getKeyStroke("F5"));
		jmiSearchNext.setAccelerator(KeyStroke.getKeyStroke("control F5"));
		jmiReplace.setAccelerator(KeyStroke.getKeyStroke("F6"));

		helpMenu.add(jmiAbout = MenuFactory.createMenuItem("About", null, null,
				0, 0, this));

		componentMenu.add(jmiAddComponent = MenuFactory.createMenuItem(
				"Add Component", null, null, 0, 0, this));
		componentMenu.add(jmiRemoveComponent = MenuFactory.createMenuItem(
				"Remove Component", null, null, 0, 0, this));
		componentMenu.add(jmiEditComponent = MenuFactory.createMenuItem(
				"Edit Component", null, null, 0, 0, this));
		componentMenu.addSeparator();
		componentMenu.add(jmiAddTask = MenuFactory.createMenuItem("Add Task",
				null, null, 0, 0, this));
		componentMenu.add(jmiRemoveTask = MenuFactory.createMenuItem(
				"Remove Task", null, null, 0, 0, this));
		componentMenu.add(jmiEditTask = MenuFactory.createMenuItem("Edit Task",
				null, null, 0, 0, this));

		algoMenu.add(jmiAlgoPeriodic = MenuFactory.createMenuItem(
				"compute PRM interface", null, null, 0, 0, this));
		algoMenu.add(jmiAlgoEDP = MenuFactory.createMenuItem("compute EDP interface", null,
				null, 0, 0, this));
		algoMenu.add(jmiAlgoEQV = MenuFactory.createMenuItem("compute EQV interface", null,
				null, 0, 0, this));
		algoMenu.add(jmiAlgoMPR = MenuFactory.createMenuItem("compute MPR interface", null,
				null, 0, 0, this));
		algoMenu.add(jmiAlgoDMPR = MenuFactory.createMenuItem("compute DMPR interface", null,
				null, 0, 0, this));
		algoMenu.add(jmiAlgoCADMPR_TASKCENTRIC = MenuFactory.createMenuItem("compute CADMPR_TASKCENTRIC interface", null,
				null, 0, 0, this));
		algoMenu.add(jmiAlgoCADMPR_MODELCENTRIC = MenuFactory.createMenuItem("compute CADMPR_MODELCENTRIC interface", null,
				null, 0, 0, this));
		algoMenu.add(jmiAlgoCADMPR_HYBRID = MenuFactory.createMenuItem("compute CADMPR_HYBRID interface", null,
				null, 0, 0, this));
//		algoMenu.add(jmiAlgoArinc = MenuFactory.createMenuItem("Apply ARINC",
//				null, null, 0, 0, this));

//		algoMenu.add(jmiAlgoSirap = MenuFactory.createMenuItem("Apply SIRAP",
//				null, null, 0, 0, this));

		jpopupmenu.add(jmiPopUndo = MenuFactory.createMenuItem("Undo", null,
				UndO, 'Z', 0, this));
		jpopupmenu.add(jmiPopRedo = MenuFactory.createMenuItem("Redo", null,
				RedO, 'Y', 0, this));
		jpopupmenu.addSeparator();
		jpopupmenu.add(MenuFactory.createMenuItem("Select All", null, null,
				'A', 0, this));
		jpopupmenu.addSeparator();
		jpopupmenu.add(jmiPopCut = MenuFactory.createMenuItem("Cut", null, null,
				'X', 0, this));
		jpopupmenu.add(jmiPopCopy = MenuFactory.createMenuItem("Copy", null,
				Copy, 'C', 0, this));
		jpopupmenu.add(jmiPopPaste = MenuFactory.createMenuItem("Paste", null,
				Paste, 'V', 0, this));

		// Change defaults so that all new tree components will have new icons
		UIManager.put("Tree.leafIcon",  new ImageIcon("images"+fileSep+leafString));
		UIManager.put("Tree.expandedIcon", new ImageIcon("images"+fileSep+expandedString));
		UIManager.put("Tree.collapsedIcon", new ImageIcon("images"+fileSep+collapsedString));
		UIManager.put("Tree.openIcon", new ImageIcon("images"+fileSep+openString));
		UIManager.put("Tree.closedIcon", new ImageIcon("images"+fileSep+closedString));

		componentTabbedPane = new CloseTabbedPane();
		componentTabbedPane.setTabLayoutPolicy(1);
		componentTabbedPane.setTabPlacement(tabplacement);
		componentTabbedPane.setFont(SYSTEM_FONT);
		componentTabbedPane.addMouseListener(this);
		componentTabbedPane.addChangeListener(this);

		sampleEditor.getTextArea().setTransferHandler(new DropHandler(this));
		sampleEditor.getTextArea().setTokenMarker(new JavaTokenMarker());
		sampleEditor.getTextArea().setRightClickPopup(jpopupmenu);
		sampleEditor.getTextArea().setRequestFocusEnabled(true);
		sampleEditor.getTextArea().addCaretListener(new CaretListenerLabel());
		sampleEditor.getTextArea().getDocument().addDocumentListener(
				new jpeDocListener(this));
		sampleEditor.getTextArea().getDocument().addUndoableEditListener(this);
		sampleEditor.getTextArea().setMagicCaretPosition(0);
		sampleEditor.getTextArea().setTabSize(2);
		sampleEditor.getTextArea().getInputHandler().addKeyBinding("C+X",
				new cutAction(this));
		sampleEditor.getTextArea().getInputHandler().addKeyBinding("C+C",
				new copyAction(this));
		sampleEditor.getTextArea().getInputHandler().addKeyBinding("C+V",
				new pasteAction(this));
		sampleEditor.getTextArea().getInputHandler().addKeyBinding("C+A",
				new selectAllAction(this));
		sampleEditor.getTextArea().getInputHandler().addKeyBinding("A+F",
				new file());
		sampleEditor.getTextArea().getInputHandler().addKeyBinding("A+E",
				new edit());
		sampleEditor.getTextArea().getInputHandler().addKeyBinding("A+S",
				new search());
		sampleEditor.getTextArea().getInputHandler().addKeyBinding("C+O",
				new openAction(this));
		sampleEditor.getTextArea().getInputHandler().addKeyBinding("C+N",
				new newAction(this));
		sampleEditor.getTextArea().getInputHandler().addKeyBinding("C+S",
				new saveAction(this));
		sampleEditor.getTextArea().getInputHandler().addKeyBinding("C+W",
				new closeAction(this));
		sampleEditor.getTextArea().getInputHandler().addKeyBinding("C+Q",
				new quitAction(this));
		sampleEditor.getTextArea().getInputHandler().addKeyBinding("C+Z",
				new undoAction(this));
		sampleEditor.getTextArea().getInputHandler().addKeyBinding("C+Y",
				new redoAction(this));
		sampleEditor.getTextArea().getInputHandler().addKeyBinding("S+TAB",
				new backTabAction(this));
		sampleEditor.getTextArea().getInputHandler().addKeyBinding("F5",
				new searchAction(this));
		sampleEditor.getTextArea().getInputHandler().addKeyBinding("F6",
				new replaceAction(this));
		sampleEditor.getTextArea().getInputHandler().addKeyBinding("C+F5",
				new searchNextAction(this));
		sampleEditor.getTextArea().getInputHandler().addKeyBinding("ENTER",
				new enterAction(this));

		jpButtons = new JToolBar();
		jpButtons.setFloatable(false);
		JToolMain = new JPanel();
		JtoolBar = new JPanel(); 

		jpButtons.setLayout(new FlowLayout(0, 0, 0));
		jpButtons.add(jbtNew = ButtonFactory.createButton(New, "New", this));
		jpButtons.addSeparator(r);
		jpButtons.add(jbtOpen = ButtonFactory.createButton(Open, "Open", this));
		jpButtons.addSeparator(r);
		jpButtons.add(jbtSave = ButtonFactory.createButton(Save, "Save File",
				this));
		jpButtons.add(jbtSaveAll = ButtonFactory.createButton(saveAll,
				"Save All", this));
		jpButtons.add(jbtSaveAs = ButtonFactory.createButton(SaveAs, "Save As",
				this));
		jpButtons.addSeparator(r);
		jpButtons.add(jbtUndo = ButtonFactory.createButton(Undo, "Undo", this));
		jpButtons.add(jbtRedo = ButtonFactory.createButton(Redo, "Redo", this));
		jpButtons.addSeparator(r);
		jpButtons.add(jbtPrint = ButtonFactory.createButton(Print, "Print", this));
		jpButtons.addSeparator(r);
		jpButtons.add(jbtSearch = ButtonFactory.createButton(Search, "Find", this));
		jpButtons.add(jbtReplace = ButtonFactory.createButton(Replace, "Replace", this));
		jpButtons.addSeparator(r);
		jpButtons.add(jbtCopy = ButtonFactory.createButton(Copy, "Copy", this));
		jpButtons.add(jbtCut = ButtonFactory.createButton(Cut, "Cut", this));
		jpButtons.add(jbtPaste = ButtonFactory.createButton(Paste, "Paste",	this));
		jpButtons.addSeparator(r);
		jpButtons.add(jbtConvertForward = ButtonFactory.createButton(
				ConvertForward, "Convert to Tree Structure", this));
		jpButtons.add(jbtConvertBackward = ButtonFactory.createButton(
				ConvertBackward, "Convert to XML File", this));
		jpButtons.addSeparator(r);

		JPanel JtoolBar2 = new JPanel();
		JtoolBar2.setLayout(new FlowLayout(FlowLayout.LEFT, 5, 0));
		JToolMain.setLayout(new BoxLayout(JToolMain, BoxLayout.Y_AXIS));
		JToolMain.add(Box.createVerticalGlue());
		JToolMain.add(JtoolBar);
		JToolMain.add(Box.createVerticalGlue());
		JToolMain.add(JtoolBar2);
		JToolMain.add(Box.createVerticalGlue());
		JtoolBar.setLayout(new FlowLayout(FlowLayout.LEFT, 5, 0));
		JtoolBar.add(jpButtons);

		jpeStatusBar = new JLabel();
		jpeStatusBar.setFont(SYSTEM_FONT);
		jpeStatusBar.setIcon(new ImageIcon("images"+fileSep+clockdis));
		jpeStatusBar.setToolTipText("Auto save disabled");
		jpeStatusBar.setIconTextGap(10);

		JPanel statusInfo = new JPanel();
		statusInfo.setLayout(new FlowLayout(FlowLayout.CENTER, 5, 2));
		statusInfo.setBorder(new EtchedBorder(EtchedBorder.LOWERED));
		statusInfo.add(jpeStatusBar);

		statusPanel = new JPanel();
		statusPanel.setLayout(new FlowLayout(FlowLayout.RIGHT, 2, 2));
		statusPanel.setBorder(new EtchedBorder(EtchedBorder.RAISED));
		statusPanel.add(statusInfo);

		getContentPane().setLayout(new BorderLayout());
		getContentPane().add(JToolMain, BorderLayout.NORTH);
		getContentPane().add(componentTabbedPane, BorderLayout.CENTER);
		getContentPane().add(statusPanel, BorderLayout.SOUTH);

		jbtRedo.setDisabledIcon(new ImageIcon("images"+fileSep+"redodis.gif"));
		jbtUndo.setDisabledIcon(new ImageIcon("images"+fileSep+"undodis.gif"));
		//jmiRedo.setDisabledIcon(new ImageIcon("images"+fileSep+"redosubdis.gif"));
		//jmiRedoAll.setDisabledIcon(new ImageIcon("images"+fileSep+"redoalldis.gif"));
		//jmiUndo.setDisabledIcon(new ImageIcon("images"+fileSep+"undosubdis.gif"));
		//jmiUndoAll.setDisabledIcon(new ImageIcon("images"+fileSep+"undoalldis.gif"));
		jbtSave.setDisabledIcon(new ImageIcon("images"+fileSep+"savedis.gif"));
		jbtSaveAll.setDisabledIcon(new ImageIcon("images"+fileSep+"savealldis.gif"));
		//jmiSave.setDisabledIcon(new ImageIcon("images"+fileSep+"savedis.gif"));
		//jmiSaveAll.setDisabledIcon(new ImageIcon("images"+fileSep+"savealldis.gif"));
		//jmiPopRedo.setDisabledIcon(new ImageIcon("images"+fileSep+"redosubdis.gif"));
		//jmiPopUndo.setDisabledIcon(new ImageIcon("images"+fileSep+"undosubdis.gif"));

		disableEditor();
		setCursor();
		setPrefs();
		this.setSize(appWidth, appHeight);
	}

	/**
	 * Disables the editor elements of the GUI when no file is opened in the
	 * tool
	 */
	private void disableEditor() {
		jmiSave.setEnabled(false);
		jbtSave.setEnabled(false);

		jmiSaveAll.setEnabled(false);
		jbtSaveAll.setEnabled(false);

		jmiSaveAs.setEnabled(false);
		jbtSaveAs.setEnabled(false);

		jmiPrint.setEnabled(false);
		jbtPrint.setEnabled(false);

		jmiClose.setEnabled(false);
		jmiCloseAll.setEnabled(false);

		jmiUndo.setEnabled(false);
		jbtUndo.setEnabled(false);
		jmiUndoAll.setEnabled(false);

		jmiRedo.setEnabled(false);
		jbtRedo.setEnabled(false);
		jmiRedoAll.setEnabled(false);

		jmiPopUndo.setEnabled(false);
		jmiPopRedo.setEnabled(false);

		jmiSearchNext.setEnabled(false);
		jmiSearch.setEnabled(false);
		jmiReplace.setEnabled(false);

		jbtSearch.setEnabled(false);
		jbtReplace.setEnabled(false);

		jmiCopy.setEnabled(false);
		jbtCopy.setEnabled(false);

		jmiCut.setEnabled(false);
		jbtCut.setEnabled(false);

		jmiPaste.setEnabled(false);
		jbtPaste.setEnabled(false);

		jmiSelectAll.setEnabled(false);

		jbtConvertBackward.setEnabled(false);
		jbtConvertForward.setEnabled(false);

		jmiAddComponent.setEnabled(false);
		jmiAddTask.setEnabled(false);
		jmiRemoveComponent.setEnabled(false);
		jmiRemoveTask.setEnabled(false);
		jmiEditComponent.setEnabled(false);
		jmiEditTask.setEnabled(false);

		jmiAlgoPeriodic.setEnabled(false);
		jmiAlgoEDP.setEnabled(false);
		jmiAlgoEQV.setEnabled(false);
		
		jmiAlgoDMPR.setEnabled(false);
		jmiAlgoMPR.setEnabled(false);
		jmiAlgoCADMPR_TASKCENTRIC.setEnabled(false);
		jmiAlgoCADMPR_MODELCENTRIC.setEnabled(false);
		jmiAlgoCADMPR_HYBRID.setEnabled(false);
//		jmiAlgoArinc.setEnabled(false);
//		jmiAlgoSirap.setEnabled(false);
	}

	/**
	 * Enables the GUI elements when any file is opened or a new file is being
	 * created
	 */
	private void enableEditor() {
		jmiSave.setEnabled(true);
		jbtSave.setEnabled(true);

		jmiSaveAll.setEnabled(true);
		jbtSaveAll.setEnabled(true);

		jmiSaveAs.setEnabled(true);
		jbtSaveAs.setEnabled(true);

		jmiPrint.setEnabled(true);
		jbtPrint.setEnabled(true);

		jmiClose.setEnabled(true);
		jmiCloseAll.setEnabled(true);

		jmiUndo.setEnabled(true);
		jbtUndo.setEnabled(true);
		jmiUndoAll.setEnabled(true);

		jmiRedo.setEnabled(true);
		jbtRedo.setEnabled(true);
		jmiRedoAll.setEnabled(true);

		jmiPopUndo.setEnabled(true);
		jmiPopRedo.setEnabled(true);

		jmiSearchNext.setEnabled(true);
		jmiSearch.setEnabled(true);
		jmiReplace.setEnabled(true);

		jbtSearch.setEnabled(true);
		jbtReplace.setEnabled(true);

		jmiCopy.setEnabled(true);
		jbtCopy.setEnabled(true);

		jmiCut.setEnabled(true);
		jbtCut.setEnabled(true);

		jmiPaste.setEnabled(true);
		jbtPaste.setEnabled(true);

		jmiSelectAll.setEnabled(true);

		jbtConvertBackward.setEnabled(true);
		jbtConvertForward.setEnabled(true);

		jmiAddComponent.setEnabled(true);
		jmiAddTask.setEnabled(true);
		jmiRemoveComponent.setEnabled(true);
		jmiRemoveTask.setEnabled(true);
		jmiEditComponent.setEnabled(true);
		jmiEditTask.setEnabled(true);

		jmiAlgoPeriodic.setEnabled(true);
		jmiAlgoEDP.setEnabled(true);
		jmiAlgoDMPR.setEnabled(true);
		jmiAlgoMPR.setEnabled(true);
		jmiAlgoEQV.setEnabled(true);
		jmiAlgoCADMPR_TASKCENTRIC.setEnabled(true);
		jmiAlgoCADMPR_MODELCENTRIC.setEnabled(true);
		jmiAlgoCADMPR_HYBRID.setEnabled(true);
//		jmiAlgoArinc.setEnabled(true);
//		jmiAlgoSirap.setEnabled(true);
	}

	/* Key Listeners */
	public void keyPressed(KeyEvent e) {
	}

	public void keyReleased(KeyEvent e) {
	}

	public void keyTyped(KeyEvent e) {
	}

	/* Focus Listeners */
	public void focusLost(FocusEvent e) {
	}

	public void focusGained(FocusEvent e) {
	}

	public void processKeyEvent(KeyEvent e) {
		super.processKeyEvent(e);
	}

	public void updateCursorPos() {
		Editors[selectedTabIndex()].getTextArea().setCaretPosition(
				currentCursorPos[selectedTabIndex()]);
		GrabFocus();
	}

	public boolean saveAll() {
		int presentIndex = selectedTabIndex();
		for (int i = 0; i < tabCount(); i++) {
			if ((dirty[i]) && (fileNames[i] != null) || (fileNames[i] == null)) {
				setSelectedTabIndex(i);
				save();
			}
		}
		setSelectedTabIndex(presentIndex);
		return true;
	}

	public void closeAll() {
		boolean savefile = false;
		for (int i = 0; i < tabCount(); i++) {
			if (dirty[i]) {
				savefile = true;
			}
		}

		if (savefile) {
			int value = JOptionPane.showConfirmDialog(this,
					"Save Unsaved Files?", "Save Unsaved Files?",
					JOptionPane.YES_NO_CANCEL_OPTION);

			switch (value) {
			case JOptionPane.YES_OPTION:
				saveAll();
				closeAllTabs();

			case JOptionPane.NO_OPTION:
				closeAllTabs();

			case JOptionPane.CANCEL_OPTION:
			default:
				return;
			}
		} else {
			closeAllTabs();
		}
	}

	public void closeAllTabs() {
		int a = tabCount();
		for (int i = 0; i < a; i++) {
			close("All");
		}
	}

	public int selectedTabIndex() {
		return componentTabbedPane.getSelectedIndex();
	}

	public void setSelectedTabIndex(int i) {
		componentTabbedPane.setSelectedIndex(i);
	}

	public int tabCount() {
		return componentTabbedPane.getTabCount();
	}

	/**
	 * Adds a new tab to the tabbed pane. Also initializes the listeners for the
	 * editor
	 * 
	 * @param Title
	 *            String to be set as the title of the tab
	 */
	public void addTab(String Title) {
		Editors[EditCount] = new ComponentArea(this);
		Editors[EditCount].getTextArea().setTransferHandler(
				new DropHandler(this));
		Editors[EditCount].getTextArea().setTokenMarker(new JavaTokenMarker());
		Editors[EditCount].getTextArea().setRightClickPopup(jpopupmenu);
		Editors[EditCount].getTextArea().addCaretListener(
				new CaretListenerLabel());
		Editors[EditCount].getTextArea().getDocument().addDocumentListener(
				new jpeDocListener(this));
		Editors[EditCount].getTextArea().getDocument().addUndoableEditListener(
				this);
		Editors[EditCount].getTextArea().setMagicCaretPosition(0);
		Editors[EditCount].getTextArea().getInputHandler().addKeyBinding("C+X",
				new cutAction(this));
		Editors[EditCount].getTextArea().getInputHandler().addKeyBinding("C+C",
				new copyAction(this));
		Editors[EditCount].getTextArea().getInputHandler().addKeyBinding("C+V",
				new pasteAction(this));
		Editors[EditCount].getTextArea().getInputHandler().addKeyBinding("C+A",
				new selectAllAction(this));
		Editors[EditCount].getTextArea().getInputHandler().addKeyBinding("A+F",
				new file());
		Editors[EditCount].getTextArea().getInputHandler().addKeyBinding("A+E",
				new edit());
		Editors[EditCount].getTextArea().getInputHandler().addKeyBinding("A+S",
				new search());
		Editors[EditCount].getTextArea().getInputHandler().addKeyBinding("C+O",
				new openAction(this));
		Editors[EditCount].getTextArea().getInputHandler().addKeyBinding("C+N",
				new newAction(this));
		Editors[EditCount].getTextArea().getInputHandler().addKeyBinding("C+S",
				new saveAction(this));
		Editors[EditCount].getTextArea().getInputHandler().addKeyBinding("C+W",
				new closeAction(this));
		Editors[EditCount].getTextArea().getInputHandler().addKeyBinding("C+Q",
				new quitAction(this));
		Editors[EditCount].getTextArea().getInputHandler().addKeyBinding("C+Z",
				new undoAction(this));
		Editors[EditCount].getTextArea().getInputHandler().addKeyBinding("C+Y",
				new redoAction(this));
		Editors[EditCount].getTextArea().getInputHandler().addKeyBinding(
				"S+TAB", new backTabAction(this));
		Editors[EditCount].getTextArea().getInputHandler().addKeyBinding("F5",
				new searchAction(this));
		Editors[EditCount].getTextArea().getInputHandler().addKeyBinding("F6",
				new replaceAction(this));
		Editors[EditCount].getTextArea().getInputHandler().addKeyBinding(
				"C+F5", new searchNextAction(this));
		Editors[EditCount].getTextArea().getInputHandler().addKeyBinding(
				"ENTER", new enterAction(this));

		undo[EditCount] = new UndoManager();
		currentCursorPos[EditCount] = 0;

		undo[EditCount].setLimit(UndoLimit);
		Editors[EditCount].getTextArea().setTabSize(tabs);
		Editors[EditCount].getTextArea().setEditable(true);

		if (Title.equals("Untitled")) {
			String count = Integer.toString(untitled);
			componentTabbedPane.addTab(Title + " " + count + ".xml     ",
					new ImageIcon("images"+fileSep+Save), Editors[EditCount].getComponent(), Title
							+ Integer.toString(untitled));
			++untitled;
		} else {
			componentTabbedPane.addTab(Title + "     ", new ImageIcon("images"+fileSep+Save),
					Editors[EditCount].getComponent(), Title);
		}

		componentTabbedPane.setSelectedIndex(EditCount);
		dirty[EditCount] = false;
		readOnly[EditCount] = false;

		copyPrefs();
		Editors[EditCount].getTextArea().setRequestFocusEnabled(true);
		componentTabbedPane.requestFocusInWindow();
		Editors[EditCount].getTextArea().requestFocusInWindow();
		Editors[EditCount].getTextArea().setCaretPosition(a);
		componentTabbedPane.setForegroundAt(EditCount, Color.blue);
		EditCount = EditCount + 1;
	}

	public void removeTab(int tabIndex) {
		componentTabbedPane.removeTabAt(tabIndex);
		System.gc();
		EditCount = EditCount - 1;
		if (tabCount() > 0) {
			Editors[selectedTabIndex()].getTextArea().grabFocus();
		}
	}

	public SyntaxDocument getDocument() {
		return Editors[selectedTabIndex()].getTextArea().getDocument();
	}

	public void setCoStatus(String s) {
		jpeStatusBar.setText(s);
	}

	private void setCursor() {
		getGlassPane().addMouseListener(new MouseAdapter() {
		});
		getGlassPane()
				.setCursor(Cursor.getPredefinedCursor(Cursor.WAIT_CURSOR));
		getGlassPane().setVisible(false);
	}

	public void setWaitCursor() {
		getGlassPane().setVisible(true);
	}

	public void setTextCursor() {
		getGlassPane().setVisible(false);
	}

	private void updateCaption() {
		String caption;
		if (fileNames[selectedTabIndex()] != null) {
			caption = new String(currFileTypes[selectedTabIndex()].getName());
			componentTabbedPane.setToolTipTextAt(selectedTabIndex(),
					fileNames[selectedTabIndex()]);
			componentTabbedPane.setTitleAt(selectedTabIndex(), caption
					+ "     ");
		}
		this.setTitle("Compositional Analysis of Real-Time Systems");
	}

	private void changeTabIcon() {
		if (dirty[selectedTabIndex()] && (!readOnly[selectedTabIndex()])) {
			componentTabbedPane.setIconAt(selectedTabIndex(), new ImageIcon("images"+fileSep+dirtyString));
			jmiSave.setEnabled(true);
			jbtSave.setEnabled(true);
			jmiSaveAll.setEnabled(true);
			jbtSaveAll.setEnabled(true);
		} else {
			componentTabbedPane.setIconAt(selectedTabIndex(), new ImageIcon("images"+fileSep+Save));
			jmiSave.setEnabled(false);
			jbtSave.setEnabled(false);
			jmiSaveAll.setEnabled(false);
			jbtSaveAll.setEnabled(false);
		}
	}

	private void copyPrefs() {
		Editors[selectedTabIndex()].getTextArea().getPainter()
				.setSelectionColor(
						sampleEditor.getTextArea().getPainter()
								.getSelectionColor());
		Editors[selectedTabIndex()].getTextArea().setTabSize(
				sampleEditor.getTextArea().getTabSize());
		Editors[selectedTabIndex()].getTextArea().getPainter().setCaretColor(
				sampleEditor.getTextArea().getPainter().getCaretColor());
		Editors[selectedTabIndex()].getTextArea().getPainter()
				.setBracketHighlightColor(
						sampleEditor.getTextArea().getPainter()
								.getBracketHighlightColor());
		Editors[selectedTabIndex()].getTextArea().getPainter()
				.setLineHighlightColor(
						sampleEditor.getTextArea().getPainter()
								.getLineHighlightColor());
		Editors[selectedTabIndex()].getTextArea().getPainter()
				.setBlockCaretEnabled(
						sampleEditor.getTextArea().getPainter()
								.isBlockCaretEnabled());
		Editors[selectedTabIndex()].getTextArea().getPainter()
				.setInvalidLinesPainted(
						sampleEditor.getTextArea().getPainter()
								.getInvalidLinesPainted());
		Editors[selectedTabIndex()].getTextArea().getPainter()
				.setEOLMarkersPainted(
						sampleEditor.getTextArea().getPainter()
								.getEOLMarkersPainted());
		Editors[selectedTabIndex()].getTextArea().getPainter()
				.setLineHighlightEnabled(
						sampleEditor.getTextArea().getPainter()
								.isLineHighlightEnabled());
		Editors[selectedTabIndex()].getTextArea().getPainter()
				.setBracketHighlightEnabled(
						sampleEditor.getTextArea().getPainter()
								.isBracketHighlightEnabled());
		Editors[selectedTabIndex()].getTextArea().setCaretBlinkEnabled(
				sampleEditor.getTextArea().isCaretBlinkEnabled());
		Editors[selectedTabIndex()].getTextArea().getGutter().setCollapsed(
				sampleEditor.getTextArea().getGutter().isCollapsed());
		Editors[selectedTabIndex()].getTextArea().getGutter().setGutterWidth(
				sampleEditor.getTextArea().getGutter().getGutterWidth());
		Editors[selectedTabIndex()].getTextArea().getGutter().setForeground(
				sampleEditor.getTextArea().getGutter().getForeground());
		Editors[selectedTabIndex()].getTextArea().getGutter().setBackground(
				sampleEditor.getTextArea().getGutter().getBackground());
		Editors[selectedTabIndex()].getTextArea().getGutter()
				.setHighlightedForeground(
						sampleEditor.getTextArea().getGutter()
								.getHighlightedForeground());
		Editors[selectedTabIndex()].getTextArea().getGutter()
				.setHighlightInterval(
						sampleEditor.getTextArea().getGutter()
								.getHighlightInterval());
		Editors[selectedTabIndex()].getTextArea().getPainter().setFont(
				sampleEditor.getTextArea().getPainter().getFont());
		Editors[selectedTabIndex()].getTextArea().getGutter().setFont(
				new Font("Monospaced", Font.BOLD, 11));
		Editors[selectedTabIndex()].getTextArea().updateScrollBars();

	}

	private void updatePrefs() {
		for (int i = 0; i < tabCount(); i++) {

			Editors[i].getTextArea().getPainter().setSelectionColor(
					Editors[selectedTabIndex()].getTextArea().getPainter()
							.getSelectionColor());
			Editors[i].getTextArea().setTabSize(
					Editors[selectedTabIndex()].getTextArea().getTabSize());
			Editors[i].getTextArea().getPainter().setCaretColor(
					Editors[selectedTabIndex()].getTextArea().getPainter()
							.getCaretColor());
			Editors[i].getTextArea().getPainter().setBracketHighlightColor(
					Editors[selectedTabIndex()].getTextArea().getPainter()
							.getBracketHighlightColor());
			Editors[i].getTextArea().getPainter().setLineHighlightColor(
					Editors[selectedTabIndex()].getTextArea().getPainter()
							.getLineHighlightColor());
			Editors[i].getTextArea().getPainter().setBlockCaretEnabled(
					Editors[selectedTabIndex()].getTextArea().getPainter()
							.isBlockCaretEnabled());
			Editors[i].getTextArea().getPainter().setInvalidLinesPainted(
					Editors[selectedTabIndex()].getTextArea().getPainter()
							.getInvalidLinesPainted());
			Editors[i].getTextArea().getPainter().setEOLMarkersPainted(
					Editors[selectedTabIndex()].getTextArea().getPainter()
							.getEOLMarkersPainted());
			Editors[i].getTextArea().getPainter().setLineHighlightEnabled(
					Editors[selectedTabIndex()].getTextArea().getPainter()
							.isLineHighlightEnabled());
			Editors[i].getTextArea().getPainter().setBracketHighlightEnabled(
					Editors[selectedTabIndex()].getTextArea().getPainter()
							.isBracketHighlightEnabled());
			Editors[i].getTextArea().setCaretBlinkEnabled(
					Editors[selectedTabIndex()].getTextArea()
							.isCaretBlinkEnabled());
			Editors[i].getTextArea().getGutter().setCollapsed(
					Editors[selectedTabIndex()].getTextArea().getGutter()
							.isCollapsed());
			Editors[i].getTextArea().getGutter().setGutterWidth(
					Editors[selectedTabIndex()].getTextArea().getGutter()
							.getGutterWidth());
			Editors[i].getTextArea().getGutter().setForeground(
					Editors[selectedTabIndex()].getTextArea().getGutter()
							.getForeground());
			Editors[i].getTextArea().getGutter().setBackground(
					Editors[selectedTabIndex()].getTextArea().getGutter()
							.getBackground());
			Editors[i].getTextArea().getGutter().setHighlightedForeground(
					Editors[selectedTabIndex()].getTextArea().getGutter()
							.getHighlightedForeground());
			Editors[i].getTextArea().getGutter().setHighlightInterval(
					Editors[selectedTabIndex()].getTextArea().getGutter()
							.getHighlightInterval());
			Editors[i].getTextArea().getPainter().setFont(
					Editors[selectedTabIndex()].getTextArea().getPainter()
							.getFont());
			Editors[i].getTextArea().getGutter().setFont(
					new Font("Monospaced", Font.BOLD, 11));
			Editors[i].getTextArea().updateScrollBars();

		}
	}

	private void setPrefs() {
		p = new Properties(System.getProperties());
		if (!(new File("prefs" +fileSep+ jpeprops).exists())) {
			System.out
					.println("Error reading Properties files - using defaults ");
			Utils
					.writeErrorLog("Error reading Properties files - using defaults ");
			restoreDefaults();
		} else {
			try {
				FileInputStream propFile = new FileInputStream("prefs" +fileSep+ jpeprops);
				p.load(propFile);
				System.setProperties(p);
			} catch (IOException ex) {
				System.out.println("Error reading properties "
						+ ex.getMessage());
				Utils.userMessage("Error", SYSTEM_ERROR, 1);
				Utils.writeErrorLog("Error reading properties "
						+ ex.getMessage());
				restoreDefaults();
			}

			tabplacement = Integer.parseInt(System.getProperty("jpe.tabpos",
					"1"));

			componentTabbedPane.setTabPlacement(tabplacement);
			textHighlightColor = new Color(new Integer(System.getProperty(
					"jpe.texthighlight", "-3355393")).intValue());
			sampleEditor.getTextArea().getPainter().setSelectionColor(
					textHighlightColor);

			caretColor = new Color(new Integer(System.getProperty(
					"jpe.caretcolour", "-16776961")).intValue());
			sampleEditor.getTextArea().getPainter().setCaretColor(caretColor);

			bracketColor = new Color(new Integer(System.getProperty(
					"jpe.bracketcolour", "-65536")).intValue());
			sampleEditor.getTextArea().getPainter().setBracketHighlightColor(
					bracketColor);

			highlightColor = new Color(new Integer(System.getProperty(
					"jpe.highlightcolour", "-2039584")).intValue());
			sampleEditor.getTextArea().getPainter().setLineHighlightColor(
					highlightColor);

			if (System.getProperty("jpe.blockcaret", "no").equals("yes")) {
				sampleEditor.getTextArea().getPainter().setBlockCaretEnabled(
						true);
			}

			if (System.getProperty("jpe.invalidlines", "no").equals("yes")) {
				sampleEditor.getTextArea().getPainter().setInvalidLinesPainted(
						true);
			}

			if (System.getProperty("jpe.eolmarker", "no").equals("yes")) {
				sampleEditor.getTextArea().getPainter().setEOLMarkersPainted(
						true);
			}

			if (System.getProperty("jpe.linehighlight", "yes").equals("yes")) {
				sampleEditor.getTextArea().getPainter()
						.setLineHighlightEnabled(true);
			}

			if (System.getProperty("jpe.brackethighlight", "yes").equals("yes")) {
				sampleEditor.getTextArea().getPainter()
						.setBracketHighlightEnabled(true);
			}

			if (System.getProperty("jpe.caretblink", "no").equals("yes")) {
				sampleEditor.getTextArea().setCaretBlinkEnabled(true);
			}

			if (System.getProperty("jpe.gutter", "no").equals("yes")) {
				sampleEditor.getTextArea().getGutter().setCollapsed(false);
			}

			if (System.getProperty("jpe.readonlynotify", "no").equals("yes")) {
				readonlynotify = true;
			}

			if (System.getProperty("jpe.autosave", "no").equals("yes")) {
				jpeStatusBar.setIcon(new ImageIcon("images/"+fileSep+clock));
			}

			UndoLimit = Integer.parseInt(System.getProperty("jpe.undolimit",
					"50"));

			tabs = Integer.parseInt(System.getProperty("jpe.tabs", "2"));

			gutwidth = Integer.parseInt(System.getProperty("jpe.gutterwidth",
					"30"));
			sampleEditor.getTextArea().getGutter().setGutterWidth(gutwidth);

			gutterFor = new Color(new Integer(System.getProperty(
					"jpe.gutterfore", "-5592406")).intValue());
			sampleEditor.getTextArea().getGutter().setForeground(gutterFor);

			gutterBak = new Color(new Integer(System.getProperty(
					"jpe.gutterback", "-1")).intValue());
			sampleEditor.getTextArea().getGutter().setBackground(gutterBak);

			gutterHigh = new Color(new Integer(System.getProperty(
					"jpe.gutterhighlight", "-12105913")).intValue());
			sampleEditor.getTextArea().getGutter().setHighlightedForeground(
					gutterHigh);

			sampleEditor.getTextArea().getGutter()
					.setHighlightInterval(
							Integer.parseInt(System.getProperty(
									"jpe.gutterint", "10")));
			gutint = Integer
					.parseInt(System.getProperty("jpe.gutterint", "10"));

			if (System.getProperty("jpe.dir", "no").equals("no")) {
			} else {
				dir = System.getProperty("jpe.dir");
			}

			appWidth = Integer.parseInt(System.getProperty("jpe.width", "800"));

			appHeight = Integer.parseInt(System
					.getProperty("jpe.height", "600"));

			if (System.getProperty("jpe.checkfilemod", "no").equals("yes")) {
				checkfilemod = true;
			} else {
				checkfilemod = false;
			}
		}
	}

	public void windowStateChanged(WindowEvent e) {
	}

	public void windowOpened(WindowEvent e) {
	}

	public void windowClosing(WindowEvent e) {
	}

	public void windowClosed(WindowEvent e) {
	}

	public void windowIconified(WindowEvent e) {
	}

	public void windowDeiconified(WindowEvent e) {
	}

	public void windowActivated(WindowEvent e) {
	}

	public void windowDeactivated(WindowEvent e) {
	}

	public void componentHidden(ComponentEvent e) {
	}

	public void componentMoved(ComponentEvent e) {
	}

	public void componentShown(ComponentEvent e) {
	}

	public void componentResized(ComponentEvent e) {
	}

	/**
	 * This method is called when an event happens in the editor area
	 */
	public void stateChanged(ChangeEvent e) {
		if (componentTabbedPane.getTabCount() > 0) {
			enableEditor();
			setUndoRedo();
			updateCursorPos();
			changeTabIcon();
			updateCaption();
			Editors[selectedTabIndex()].getTextArea().grabFocus();
			checkReadOnly();
			for (int i = 0; i < tabCount(); i++) {
				componentTabbedPane.setForegroundAt(i, Color.BLACK);
			}
			componentTabbedPane.setForegroundAt(selectedTabIndex(), Color.blue);
		} else {
			disableEditor();
		}
	}

	public void checkReadOnly() {
		if (selectedTabIndex() >= 0) {
			if (readOnly[selectedTabIndex()]) {
				Editors[selectedTabIndex()].getTextArea().setEditable(false);
				Editors[selectedTabIndex()].getTextArea().getPainter()
						.setBackgroundColor(new Color(192, 192, 192));
			} else {
				Editors[selectedTabIndex()].getTextArea().setEditable(true);
				Editors[selectedTabIndex()].getTextArea().getPainter()
						.setBackgroundColor(Color.white);
			}
		}
	}

	/**
	 * This method makes sure a new line is present in the end of the file as
	 * JPE editor needs it to display the last line
	 * 
	 * @param fileName
	 */
	protected void checkForNewLine(String fileName) {
		try {
			FileInputStream fileStream = new FileInputStream(fileName);
			int numChars = fileStream.available();
			fileStream.skip(numChars - 1);
			int lastChar = fileStream.read();
			fileStream.close();
			if (lastChar != 10) {
				System.err.println("Adding a new line in the end");
				FileOutputStream fileOutStream = new FileOutputStream(fileName,
						true);
				fileOutStream.write(10);
				fileOutStream.close();
			}
		} catch (FileNotFoundException e) {
			e.printStackTrace();
		} catch (IOException e) {
			e.printStackTrace();
		}
	}

	public void mousePressed(MouseEvent e) {
		if (((e.getModifiers() & InputEvent.BUTTON3_MASK) == InputEvent.BUTTON3_MASK)
				&& (e.getSource() instanceof mbJTextArea)) {
			jpopupmenu.show(Editors[selectedTabIndex()].getTextArea(),
					e.getX(), e.getY());
		}
	}

	public void mouseClicked(MouseEvent e) {
	}

	public void mouseReleased(MouseEvent e) {
	}

	public void mouseEntered(MouseEvent e) {
		if (e.getSource() instanceof JButton) {
			JButton jbt = (JButton) e.getSource();
			if (jbt.isEnabled())
				jbt.setBorderPainted(true);
		}

		if (e.getSource() instanceof JToggleButton) {
			JToggleButton jtb = (JToggleButton) e.getSource();
			if (jtb.isEnabled())
				jtb.setBorderPainted(true);
		}
	}

	public void mouseExited(MouseEvent e) {
		if (e.getSource() instanceof JButton) {
			JButton jbt = (JButton) e.getSource();
			if (jbt.isEnabled())
				jbt.setBorderPainted(false);
		}

		if (e.getSource() instanceof JToggleButton) {
			JToggleButton jtb = (JToggleButton) e.getSource();
			if (jtb.isEnabled())
				jtb.setBorderPainted(false);
		}
	}

	/**
	 * Handles all the events reported. Checks the source of the event and calls
	 * the associated handler.
	 */
	//xm: Register listeners for all events! Key functions to modify to add CADMPR functions
	public void actionPerformed(ActionEvent e) {
		if (e.getSource() == jmiAbout) {
			About();
		}

		else if ((e.getSource() == jbtNew) || (e.getSource() == jmiNew)) {
			newDoc();
		}

		else if ((e.getSource() == jbtOpen) || (e.getSource() == jmiOpen)) {
			open();
			
		}

		else if ((e.getSource() == jbtSave) || (e.getSource() == jmiSave)) {
			save();
		}

		else if ((e.getSource() == jbtSaveAs) || (e.getSource() == jmiSaveAs)) {
			saveAsFile();
		}

		else if ((e.getSource() == jmiSaveAll) || (e.getSource() == jbtSaveAll)) {
			saveAll();
		}

		else if ((e.getSource() == jbtPrint) || (e.getSource() == jmiPrint)) {
			Utils.Print(Editors[selectedTabIndex()].getTextArea().getText());
			this.repaint();
		}

		else if (e.getSource() == jmiClose) {
			close("");
		}

		else if (e.getSource() == jmiCloseAll) {
			closeAll();
		}

		else if (e.getSource() == jmiQuit) {
			Quit();
		}

		else if ((e.getSource() == jbtCut) || (e.getSource() == jmiCut)
				|| (e.getSource() == jmiPopCut)) {
			Editors[selectedTabIndex()].getTextArea().cut();
		}

		else if ((e.getSource() == jbtCopy) || (e.getSource() == jmiCopy)
				|| (e.getSource() == jmiPopCopy)) {
			Editors[selectedTabIndex()].getTextArea().copy();
		}

		else if ((e.getSource() == jbtPaste) || (e.getSource() == jmiPaste)
				|| (e.getSource() == jmiPopPaste)) {
			Paste();
		}

		else if ((e.getSource() == jbtUndo) || (e.getSource() == jmiUndo)
				|| (e.getSource() == jmiPopUndo)) {
			Undo();
		}

		else if ((e.getSource() == jbtRedo) || (e.getSource() == jmiRedo)
				|| (e.getSource() == jmiPopRedo)) {
			Redo();
		}

		else if (e.getSource() == jmiUndoAll) {
			UndoAll();
		}

		else if (e.getSource() == jmiRedoAll) {
			RedoAll();
		}

		else if (e.getSource() == jbtConvertForward) {
			convertToTree();
		}

		else if (e.getSource() == jbtConvertBackward) {
			convertToXml();
		}

		else if ((e.getSource() == jbtSearch) || (e.getSource() == jmiSearch)) {
			SearchMain();
		}

		else if (e.getSource() == jmiSearchNext) {
			FindNext();
		}

		else if ((e.getSource() == jbtReplace) || (e.getSource() == jmiReplace)) {
			ReplaceMain();
		}

		else if (e.getSource() == jmiAddComponent) {
			Editors[selectedTabIndex()].getTreeArea().addCompClicked();
		} else if (e.getSource() == jmiAddTask) {
			Editors[selectedTabIndex()].getTreeArea().addTaskClicked();
		} else if (e.getSource() == jmiRemoveComponent) {
			Editors[selectedTabIndex()].getTreeArea().removeCompClicked();
		} else if (e.getSource() == jmiRemoveTask) {
			Editors[selectedTabIndex()].getTreeArea().removeTaskClicked();
		} else if (e.getSource() == jmiEditComponent) {
			Editors[selectedTabIndex()].getTreeArea().editCompClicked();
		} else if (e.getSource() == jmiEditTask) {
			Editors[selectedTabIndex()].getTreeArea().editTaskClicked();
		}

		//xm: register listener to computer DMPR interface!
		//xm: meng needs to return the components' tree's root component
		//xm: may need to use your own tree structure to parse the tree and compute interfaces
		else if (e.getSource() == jmiAlgoPeriodic) {
			Editors[selectedTabIndex()].getTreeArea().processPeriodic();
		} else if (e.getSource() == jmiAlgoEDP) {
			Editors[selectedTabIndex()].getTreeArea().processEDP();
		}else if (e.getSource() == jmiAlgoEQV) {
			Editors[selectedTabIndex()].getTreeArea().processEQV();
//		} else if (e.getSource() == jmiAlgoArinc) {
//			Editors[selectedTabIndex()].getTreeArea().processArinc();
//		} else if (e.getSource() == jmiAlgoSirap) {
//			Editors[selectedTabIndex()].getTreeArea().processSirap();
		} else if (e.getSource() == jmiAlgoDMPR) {
			Editors[selectedTabIndex()].getTreeArea().processDMPR();
		} else if (e.getSource() == jmiAlgoMPR) {
			Editors[selectedTabIndex()].getTreeArea().processMPR();
		} else if (e.getSource() == jmiAlgoCADMPR_TASKCENTRIC){ 
			Editors[selectedTabIndex()].getTreeArea().processCADMPR_TASKCENTRIC();
		} else if (e.getSource() == jmiAlgoCADMPR_MODELCENTRIC) {
			Editors[selectedTabIndex()].getTreeArea().processCADMPR_MODELCENTRIC();
		} else if (e.getSource() == jmiAlgoCADMPR_HYBRID) {
			Editors[selectedTabIndex()].getTreeArea().processCADMPR_HYBRID();
		} 
	}

	public void convertToTree() {
		if ((fileNames[selectedTabIndex()] == null)
				|| (dirty[selectedTabIndex()] == true)) {
			save();
		}
		if ((fileNames[selectedTabIndex()] != null)
				&& (dirty[selectedTabIndex()] != true)) {
			Editors[selectedTabIndex()]
					.convertToTree(fileNames[selectedTabIndex()]);
		} else {
			Frame frame = new Frame();
			JOptionPane.showMessageDialog(frame,
					"Please save the XML to a file to convert it to a Tree");
		}
	}
	public void convertToXml(){
		if ((fileNames[selectedTabIndex()] == null)
				|| (dirty[selectedTabIndex()] == true)) {
			bConvertTree=false;
			save();
			bConvertTree=true;
		}
		if ((fileNames[selectedTabIndex()] != null)
				&& (dirty[selectedTabIndex()] != true)) {
			int selectedIndex = selectedTabIndex();
			String fileName = fileNames[selectedIndex];
			Editors[selectedIndex].convertToXML(fileName);
			loadDocumentAt(fileName, selectedIndex);
		} else {
			Frame frame = new Frame();
			JOptionPane
					.showMessageDialog(frame,
							"Provide the file name to which the XML is to be written");
		}
	}
	public void Quit() {
		if (Utils.okToQuit(dirty, readOnly)) {
			writePrefs();
			Runtime.getRuntime().gc();
			dispose();
			System.exit(0);
		}
	}

	// this method resets all the text component settings to their defaults
	public boolean restoreDefaults() {
		textHighlightColor = new Color(0xccccff);
		p.setProperty("jpe.highlightcolour", new String(Integer
				.toString(textHighlightColor.getRGB())));
		caretColor = Color.blue;
		p.setProperty("jpe.caretcolour", new String(Integer.toString(caretColor
				.getRGB())));
		bracketColor = Color.red;
		p.setProperty("jpe.bracketcolour", new String(Integer
				.toString(bracketColor.getRGB())));
		highlightColor = new Color(0xe0e0e0);
		p.setProperty("jpe.highlightcolour", new String(Integer
				.toString(highlightColor.getRGB())));
		gutterFor = new Color(170, 170, 170);
		p.setProperty("jpe.gutterfore", new String(Integer.toString(gutterFor
				.getRGB())));
		gutterBak = Color.white;
		p.setProperty("jpe.gutterback", new String(Integer.toString(gutterBak
				.getRGB())));
		gutterHigh = new Color(71, 71, 71);
		p.setProperty("jpe.gutterhighlight", new String(Integer
				.toString(gutterHigh.getRGB())));
		gutwidth = 30;
		p
				.setProperty("jpe.gutterwidth", new String(Integer
						.toString(gutwidth)));
		gutint = 10;
		p.setProperty("jpe.gutterint", new String(Integer.toString(gutint)));
		p.setProperty("jpe.linehighlight", "yes");
		p.setProperty("jpe.caretblink", "yes");
		p.setProperty("jpe.gutter", "no");
		p.setProperty("jpe.brackethighlight", "yes");
		p.setProperty("jpe.invalidlines", "no");
		p.setProperty("jpe.eolmarker", "no");
		p.setProperty("jpe.blockcaret", "no");

		tabs = 2;
		p.setProperty("jpe.tabs", "2");

		if(selectedTabIndex()>=0){
		Editors[selectedTabIndex()].getTextArea().setTabSize(tabs);
		Editors[selectedTabIndex()].getTextArea().getGutter().setGutterWidth(
				gutwidth);
		Editors[selectedTabIndex()].getTextArea().getGutter()
				.setHighlightInterval(gutint);
		Editors[selectedTabIndex()].getTextArea().getPainter()
				.setBlockCaretEnabled(false);
		Editors[selectedTabIndex()].getTextArea().getPainter()
				.setEOLMarkersPainted(false);
		Editors[selectedTabIndex()].getTextArea().getPainter()
				.setInvalidLinesPainted(false);
		Editors[selectedTabIndex()].getTextArea().getPainter()
				.setLineHighlightEnabled(true);
		Editors[selectedTabIndex()].getTextArea().getPainter()
				.setBracketHighlightEnabled(true);
		Editors[selectedTabIndex()].getTextArea().setCaretBlinkEnabled(true);
		Editors[selectedTabIndex()].getTextArea().getGutter()
				.setCollapsed(true);
		updatePrefs();
		}
		return true;
	}

	private void writePrefs() {
		p.setProperty("jpe.width", Integer.toString(this.getWidth()));
		p.setProperty("jpe.height", Integer.toString(this.getHeight()));

		try {
			FileOutputStream out = new FileOutputStream("prefs"+fileSep + jpeprops);
			p.store(out, "--- Program Generated file - Do not edit! ---");
			out.close();
		}

		catch (IOException ex) {
			System.out.println("Error writing properties " + ex.getMessage());
			Utils.userMessage("Error", SYSTEM_ERROR, 1);
			Utils.writeErrorLog("Error writing properties " + ex.getMessage());
		}
	}

	// gets the current file name
	public String getcurrFileName() {
		String s = fileNames[selectedTabIndex()];
		return s;
	}

	// inserts the given string at the specified carat position
	public void insert(String s) {
		int a = Editors[selectedTabIndex()].getTextArea().getCaretPosition();
		Editors[selectedTabIndex()].getTextArea().insert(s, a);
	}

	public String getFileName() {
		return fileNames[selectedTabIndex()];
	}

	// displays the find dialog box
	public void SearchMain() {
		Editors[selectedTabIndex()].getTextArea().getFind().setVisible(true);
	}

	public void FindNext() {
		Editors[selectedTabIndex()].getTextArea().getFind().setVisible(true);
	}

	public void ReplaceMain() {
		Editors[selectedTabIndex()].getTextArea().getFind().setVisible(true);
	}

	// displays the find dialog box
	public void SearchRepNext() {
		Editors[selectedTabIndex()].getTextArea().getFind().Replace();
	}

	// gets the text contained in the document
	public String GetText() {
		String s = new String();
		try {
			s = Editors[selectedTabIndex()].getTextArea().getDocument()
					.getText(
							0,
							Editors[selectedTabIndex()].getTextArea()
									.getDocument().getLength());
		} catch (Exception ex) {
			System.out
					.println("Error getting document text " + ex.getMessage());
			Utils.userMessage("Error", SYSTEM_ERROR, 1);
			Utils
					.writeErrorLog("Error getting document text"
							+ ex.getMessage());
		}
		return s;
	}

	// returns selected text as a string
	public String getSelectedText() {
		return Editors[selectedTabIndex()].getTextArea().getSelectedText();
	}

	// misc methods for use with the text component
	// gets focus for the text area
	public void RequestFocus() {
		Editors[selectedTabIndex()].getTextArea().requestFocusInWindow();
	}

	// grabs focus for the text area
	public void GrabFocus() {
		Editors[selectedTabIndex()].getTextArea().grabFocus();
	}

	// gets focus for the application
	public void JpeRequestFocus() {
		this.requestFocusInWindow();
	}

	// selects text from a to b
	public void Select(int a, int b) {
		Editors[selectedTabIndex()].getTextArea().select(a, b);
	}

	public int getSelectionStart() {
		return Editors[selectedTabIndex()].getTextArea().getSelectionStart();
	}

	public int getSelectionEnd() {
		return Editors[selectedTabIndex()].getTextArea().getSelectionEnd();
	}

	// sets the caret position
	public void SetCaretPos(int a) {
		Editors[selectedTabIndex()].getTextArea().setCaretPosition(a);
	}

	// replaces the current selection
	public void ReplaceSelection(String t) {
		Editors[selectedTabIndex()].getTextArea().setSelectedText(t);
	}

	// gets the current font
	public Font getFont() {
		return sampleEditor.getTextArea().getPainter().getFont();
	}

	private void checkDocType(String f) {
		if ((f.endsWith(".xml")) || (f.endsWith(".XML"))) {
			Editors[selectedTabIndex()].getTextArea().setTokenMarker(
					new XMLTokenMarker());
			syntaxType[selectedTabIndex()] = "xml";
		}
	}

	// Open file (no parameters)
	public void open() {
		File curDir;
		if (selectedTabIndex() >= 0) {
			if ((fileNames[selectedTabIndex()] == null)
					|| (fileNames[selectedTabIndex()] == "")) {
				curDir=new File(dir);
			} else {
				curDir=new File(
						fileNames[selectedTabIndex()]).getParentFile();
			}
		}
		else
		{
			curDir=new File(dir);
		}
		File f[] = CartsFileChooser.openFile(this,curDir,99 - tabCount());
		if(f!=null)
		{
			for (int i = 0; i < f.length; i++) {
				open(f[i].getPath());
				convertToTree();
				//convertToXml();
			}			
		}
	}

	public void open(String f) {
		checkForNewLine(f);
		openFile(f);
	}

	public void openFile(String f) {
		if (tabCount() <= 98) {
			addTab(f);
			loadDocumentAt(f, selectedTabIndex());
		} else {
			Utils.userMessage("Document limit reached",
					"Limit of 999 open documents reached", 2);
		}
	}

	public void loadDocumentAt(String f, int index) {
		checkDocType(f);
		new Open(this, f, readonlynotify);
		fileNames[selectedTabIndex()] = f;
		currFileTypes[selectedTabIndex()] = new File(
				fileNames[selectedTabIndex()]);
		fileModified[selectedTabIndex()] = currFileTypes[selectedTabIndex()]
				.lastModified();
		dirty[selectedTabIndex()] = false;

		readOnly[selectedTabIndex()] = Utils.isReadOnly(f);

		checkReadOnly();
		updateCaption();
		changeTabIcon();
		undoManager();
		setTextCursor();

		Editors[selectedTabIndex()].getTextArea().setCaretPosition(a);
		Editors[selectedTabIndex()].getTextArea().grabFocus();
		Editors[selectedTabIndex()].getTextArea().grabFocus();
	}

	// places text into the text area
	public void loadDoc(String s) {
		Editors[selectedTabIndex()].getTextArea().setText(s);
	}

	// places text into the text area
	public void setText(String s) {
		Editors[selectedTabIndex()].getTextArea().setText(s);
	}

	// places text into the text area
	public String getText() {
		return Editors[selectedTabIndex()].getTextArea().getText();
	}

	// method for creating a new document
	public void newDoc() {
		if (tabCount() <= 98) {
			addTab("Untitled");
			Editors[selectedTabIndex()].getTextArea().setText(
					"<system os_scheduler=\"EDF\">\n</system>");
			fileNames[selectedTabIndex()] = null;
			currFileTypes[selectedTabIndex()] = new File("");
			fileModified[selectedTabIndex()] = 0;
			Editors[selectedTabIndex()].getTextArea().setTokenMarker(
					new XMLTokenMarker());
			syntaxType[selectedTabIndex()] = "xml";
			Editors[selectedTabIndex()].getTextArea().setCaretPosition(a);
			undoManager();
		} else {
			Utils.userMessage("Document limit reached",
					"Limit of 99 open documents reached", 2);
		}
	}

	// method used to close files - also resets undo manager
	public void close(String all) {
		if (all.equals("All")) {
			if (componentTabbedPane.getTabCount() == 1) {
				removeTab(selectedTabIndex());
			} else {
				for (int i = selectedTabIndex(); i < EditCount; i++) {
					Editors[i] = Editors[i + 1];
					dirty[i] = dirty[i + 1];
					readOnly[i] = readOnly[i + 1];
					fileNames[i] = fileNames[i + 1];
					fileModified[i] = fileModified[i + 1];
					currFileTypes[i] = currFileTypes[i + 1];
					undo[i] = undo[i + 1];
					currentCursorPos[i] = currentCursorPos[i + 1];
				}
				removeTab(selectedTabIndex());
				updateCaption();
				changeTabIcon();
				setUndoRedo();
				updateCursorPos();
			}
		} else {
			if (Utils.okToAbandon(dirty[selectedTabIndex()],
					readOnly[selectedTabIndex()],
					fileNames[selectedTabIndex()], componentTabbedPane
							.getTitleAt(selectedTabIndex()))) {
				if (componentTabbedPane.getTabCount() == 1) {
					removeTab(selectedTabIndex());
				} else {
					for (int i = selectedTabIndex(); i < EditCount; i++) {
						Editors[i] = Editors[i + 1];
						dirty[i] = dirty[i + 1];
						readOnly[i] = readOnly[i + 1];
						fileNames[i] = fileNames[i + 1];
						fileModified[i] = fileModified[i + 1];
						currFileTypes[i] = currFileTypes[i + 1];
						undo[i] = undo[i + 1];
						currentCursorPos[i] = currentCursorPos[i + 1];
					}
					removeTab(selectedTabIndex());
					updateCaption();
					changeTabIcon();
					setUndoRedo();
					updateCursorPos();
				}
			}
		}
	}

	// sets the current file name
	public void setcurrFileName(String s) {
		fileNames[selectedTabIndex()] = s;
	}

	// Save file
	public boolean save() {
		if (fileNames[selectedTabIndex()] == null) {
			return saveAsFile();
		} else {
			boolean temp = checkfilemod;
			if (Utils.okToOverwrite(fileNames[selectedTabIndex()],
					currFileTypes[selectedTabIndex()])) {
				SaveFile savefile = new SaveFile(this,
						fileNames[selectedTabIndex()],
						Editors[selectedTabIndex()].getTextArea().getDocument());
				dirty[selectedTabIndex()] = false;
				readOnly[selectedTabIndex()] = false;
				currFileTypes[selectedTabIndex()] = new File(
						fileNames[selectedTabIndex()]);
				fileModified[selectedTabIndex()] = currFileTypes[selectedTabIndex()]
						.lastModified();
				setTextCursor();
				updateCaption();
				changeTabIcon();
				checkfilemod = false;
				checkDocType(fileNames[selectedTabIndex()]);
				checkfilemod = temp;
				Editors[selectedTabIndex()].getTextArea().grabFocus();
				if (bConvertTree)
				{
					convertToTree();
					//convertToXml();
				}
				return true;
			}
			Editors[selectedTabIndex()].getTextArea().grabFocus();
			return false;
		}
	}

	// save file as
	public boolean saveAsFile() {
		File curDir;
		if (selectedTabIndex() >= 0) {
			if ((fileNames[selectedTabIndex()] == null)
					|| (fileNames[selectedTabIndex()] == "")) {
				curDir=new File(dir);
			} else {
				curDir=new File(
						fileNames[selectedTabIndex()]).getParentFile();
			}
		}
		else
		{
			curDir=new File(dir);
		}
		String targetFileName = componentTabbedPane
				.getTitleAt(selectedTabIndex());
		targetFileName = targetFileName.substring(0,
				targetFileName.length() - 5);
		File file=CartsFileChooser.saveFile(this, curDir,targetFileName);
		if(file!=null)
		{
			fileNames[selectedTabIndex()] = file.getPath();
			return save();
		}
		else
		{
			return false;	
		}
	}

	// displays the about box
	public void About() {
		new About();
	}

	// methods used by the document listener interface
	public void doc_changed(DocumentEvent e) {
		if (!dirty[selectedTabIndex()]) {
			dirty[selectedTabIndex()] = true;
			changeTabIcon();
		}
	}

	public void doc_insert(DocumentEvent e) {
		if (!dirty[selectedTabIndex()]) {
			dirty[selectedTabIndex()] = true;
			changeTabIcon();
		}
	}

	public void doc_remove(DocumentEvent e) {
		if (!dirty[selectedTabIndex()]) {
			dirty[selectedTabIndex()] = true;
			changeTabIcon();
		}
	}

	public mbJTextArea getEditor() {
		return Editors[selectedTabIndex()].getTextArea();
	}

	// This class listens for and reports caret movements.
	protected class CaretListenerLabel extends JLabel implements CaretListener {
		public CaretListenerLabel() {
			super();
		}

		public void caretUpdate(CaretEvent e) {
			// updateLineCount();
			currentCursorPos[selectedTabIndex()] = Editors[selectedTabIndex()]
					.getTextArea().getCaretPosition();

			int a = Editors[selectedTabIndex()].getTextArea()
					.getLineStartOffset(
							Editors[selectedTabIndex()].getTextArea()
									.getLineOfOffset(
											Editors[selectedTabIndex()]
													.getTextArea()
													.getCaretPosition()));
			int a1 = Editors[selectedTabIndex()].getTextArea()
					.getLineEndOffset(
							Editors[selectedTabIndex()].getTextArea()
									.getLineOfOffset(
											Editors[selectedTabIndex()]
													.getTextArea()
													.getCaretPosition()));
			int b = Editors[selectedTabIndex()].getTextArea().getLineOfOffset(
					Editors[selectedTabIndex()].getTextArea()
							.getCaretPosition());
			int c = Editors[selectedTabIndex()].getTextArea()
					.getCaretPosition();
			int d = Editors[selectedTabIndex()].getTextArea().getLineLength(b);
			String s = Editors[selectedTabIndex()].getTextArea().getLineText(
					Editors[selectedTabIndex()].getTextArea().getLineOfOffset(
							Editors[selectedTabIndex()].getTextArea()
									.getCaretPosition()));

			int col = c - a;
			int chars = a1 - col;

			setCoStatus("Line: "
					+ new String(Integer.toString(b + 1))
					+ " of "
					+ new String(Integer.toString(Editors[selectedTabIndex()]
							.getTextArea().getLineCount())) + " |  Col: "
					+ new String(Integer.toString(col)) + "  |  Char: "
					+ new String(Integer.toString(c)));

		}
	}

	public int getCaretLine() {
		return Editors[selectedTabIndex()].getTextArea().getLineOfOffset(
				Editors[selectedTabIndex()].getTextArea().getCaretPosition());
	}

	public int getSelectionStartLine() {
		return Editors[selectedTabIndex()].getTextArea()
				.getSelectionStartLine();
	}

	public int getSelectionEndLine() {
		return Editors[selectedTabIndex()].getTextArea().getSelectionEndLine();
	}

	public void setSelectedText(String s) {
		Editors[selectedTabIndex()].getTextArea().setSelectedText(s);
	}

	public int getCaretPosition() {
		return Editors[selectedTabIndex()].getTextArea().getCaretPosition();
	}

	private void undoManager() {
		jbtUndo.setEnabled(false);
		jbtRedo.setEnabled(false);
		jmiUndo.setEnabled(false);
		jmiUndoAll.setEnabled(false);
		jmiRedo.setEnabled(false);
		jmiRedoAll.setEnabled(false);
		jmiPopUndo.setEnabled(false);
		jmiPopRedo.setEnabled(false);
		undo[selectedTabIndex()].discardAllEdits();
	}

	private void setUndoRedo() {
		if (undo[selectedTabIndex()].canUndo()) {
			jbtUndo.setEnabled(true);
			jmiUndo.setEnabled(true);
			jmiUndoAll.setEnabled(true);
			jmiPopUndo.setEnabled(true);

		} else {
			jbtUndo.setEnabled(false);
			jmiUndo.setEnabled(false);
			jmiUndoAll.setEnabled(false);
			jmiPopUndo.setEnabled(false);
		}

		if (undo[selectedTabIndex()].canRedo()) {
			jbtRedo.setEnabled(true);
			jmiRedo.setEnabled(true);
			jmiRedoAll.setEnabled(true);
			jmiPopRedo.setEnabled(true);

		} else {
			jbtRedo.setEnabled(false);
			jmiRedo.setEnabled(false);
			jmiRedoAll.setEnabled(false);
			jmiPopRedo.setEnabled(false);
		}

	}

	public void UndoAll() {
		do {
			Undo();
		} while (undo[selectedTabIndex()].canUndo());

		jbtUndo.setEnabled(false);
		jmiUndo.setEnabled(false);
		jmiUndoAll.setEnabled(false);
		jmiPopUndo.setEnabled(false);
	}

	public void RedoAll() {
		do {
			Redo();
		} while (undo[selectedTabIndex()].canRedo());

		jbtRedo.setEnabled(false);
		jmiRedoAll.setEnabled(false);
		jmiRedo.setEnabled(false);
		jmiPopRedo.setEnabled(false);
	}

	// un-does the last action
	public void Undo() {
		if (undo[selectedTabIndex()].canUndo()) {
			undo[selectedTabIndex()].undo();
			jbtRedo.setEnabled(true);
			jmiRedo.setEnabled(true);
			jmiRedoAll.setEnabled(true);
			jmiPopRedo.setEnabled(true);

		} else {
			jbtUndo.setEnabled(false);
			jmiUndo.setEnabled(false);
			jmiUndoAll.setEnabled(false);
			jmiPopUndo.setEnabled(false);
			Utils.userMessage("Undo", "No more Undos", 1);
		}
		Editors[selectedTabIndex()].getTextArea().grabFocus();
	}

	// re-does the last action
	public void Redo() {
		if (undo[selectedTabIndex()].canRedo()) {
			undo[selectedTabIndex()].redo();
			jbtUndo.setEnabled(true);
			jmiUndo.setEnabled(true);
			jmiUndoAll.setEnabled(true);
			jmiPopUndo.setEnabled(true);

		} else {
			jbtRedo.setEnabled(false);
			jmiRedo.setEnabled(false);
			jmiRedoAll.setEnabled(false);
			jmiPopRedo.setEnabled(false);
			Utils.userMessage("Undo", "No more Redos", 1);
		}
		Editors[selectedTabIndex()].getTextArea().grabFocus();
	}

	public void undoableEditHappened(UndoableEditEvent e) {
		undo[selectedTabIndex()].addEdit(e.getEdit());
		jbtUndo.setEnabled(true);
		jmiUndo.setEnabled(true);
		jmiUndoAll.setEnabled(true);
		jmiPopUndo.setEnabled(true);
	}

	public void Paste() {
		Editors[selectedTabIndex()].getTextArea().paste();
	}

	public void selectAll() {
		Editors[selectedTabIndex()].getTextArea().selectAll();
	}

	public void checkFileModified() {
		File f = null;

		try {
			if (fileNames[selectedTabIndex()].equals("")
					|| fileNames[selectedTabIndex()] == null) {
				return;
			}
			f = new File(fileNames[selectedTabIndex()]);
		} catch (Exception e) {
			return;
		}

		long lastmod;
		Time modTime, fileModTime;
		if (f.exists()) {
			lastmod = f.lastModified();
			modTime = new Time(lastmod); // currents file mod time
			fileModTime = new Time(fileModified[selectedTabIndex()]);

			if (!(modTime.equals(fileModTime))) {
				if (Utils
						.genericConfirm(
								"This file has been modified outside of this application, Reload?",
								"File Modified")) {
					refreshCurrentDoc(f);
				} else {
					fileModified[selectedTabIndex()] = f.lastModified();
				}
			}
		}
	}

	public void refreshCurrentDoc(File f) {
		if (f.exists()) {
			int a = Editors[selectedTabIndex()].getTextArea()
					.getCaretPosition();
			// firstTime = true;
			open(fileNames[selectedTabIndex()]);
			fileModified[selectedTabIndex()] = f.lastModified();
			// firstTime = false;
			Editors[selectedTabIndex()].getTextArea().setCaretPosition(a);
		}
	}

	public class file implements ActionListener {
		public void actionPerformed(ActionEvent evt) {
			fileMenu.doClick(1);
		}
	}

	public class edit implements ActionListener {
		public void actionPerformed(ActionEvent evt) {
			editMenu.doClick(1);
		}
	}

	public class search implements ActionListener {
		public void actionPerformed(ActionEvent evt) {
			searchMenu.doClick(1);
		}
	}

	public class modAction implements ActionListener {
		public void actionPerformed(ActionEvent evt) {
			if (checkfilemod) {
				checkFileModified();
			}
		}
	}

	public void addSystemClipBoard(String p) {
		if (p.equals("Cut")) {
			Editors[selectedTabIndex()].getTextArea().cut();
		} else {
			Editors[selectedTabIndex()].getTextArea().copy();
		}
	}

	public void stopRun(boolean javacerror) {
	}
} // program end

