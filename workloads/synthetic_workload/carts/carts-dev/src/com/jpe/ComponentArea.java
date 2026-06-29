package com.jpe;

import java.awt.Frame;

import javax.swing.JFrame;
import javax.swing.JOptionPane;
import javax.swing.JSplitPane;
import edu.penn.rtg.schedulingapp.SchedulingTree;
import edu.penn.rtg.schedulingapp.input.xml.XMLInterpreter;
import edu.penn.rtg.schedulingapp.input.treeGUI.ComponentTreeUI;
import edu.penn.rtg.schedulingapp.output.Output;
import edu.penn.rtg.schedulingapp.util.UserUtil;

/**
 * Component Area class combines the editor, the tree view and the analysis
 * result. This class creates the basic Scheduling Tree object for the XML file
 * in the editor. The Scheduling Tree object is passed to the ComponentUI object
 * to present the Tree View.
 */
//xm: This class needs to be re-write! It connects the GUI (system tree view), xml and components' tree structure.
//xm: Use your new tree structure. 
//Use another class which transfer from my new tree structure to old tree structure (SchedTree) when old implementation(resource model) are used.
public class ComponentArea {
	// The top half of the UI, with Tree View and Editor components
	private JSplitPane leftRight;

	// The combination of all the components
	private JSplitPane topBottom;

	// The basic Scheduling Tree object for the XML file
	private SchedulingTree schedulingTree;

	// The Editor object
	private mbJTextArea textArea;

	// The Tree View object
	private ComponentTreeUI treeArea;

	// The Analysis Result object
	protected Output output;

	private JFrame editor;

	private void setTabs() {
		leftRight = new JSplitPane(JSplitPane.HORIZONTAL_SPLIT, true, treeArea,
				textArea);
		leftRight.setOneTouchExpandable(true);
		leftRight.setDividerSize(7);
		leftRight.setDividerLocation(400);
		setTopBottom();
	}

	private void setTopBottom() {
		topBottom = new JSplitPane(JSplitPane.VERTICAL_SPLIT, true, leftRight,
				output);
		topBottom.setOneTouchExpandable(true);
		topBottom.setDividerSize(7);
		topBottom.setDividerLocation(450);
	}

	public ComponentArea() {
		output = new Output();
		textArea = new mbJTextArea();
		schedulingTree = new SchedulingTree();
		treeArea = new ComponentTreeUI(schedulingTree, output,null);
		setTabs();
	}

	/**
	 * A new system is being created. Hence there is no second argument. As a
	 * reason, a default object of SchedulingTree is created.
	 * 
	 * @param parent
	 */
	public ComponentArea(JFrame parent) {
		output = new Output();
		textArea = new mbJTextArea(parent);
		schedulingTree = new SchedulingTree();
		treeArea = new ComponentTreeUI(schedulingTree, output, parent);
		setTabs();
		editor=parent;
	}

	/**
	 * An XML file has been opened. The file is passed to the XML Interpreter to
	 * parse and build the Scheduling Tree.
	 * 
	 * @param parent
	 * @param fileName
	 */
	public ComponentArea(JFrame parent, String fileName) {
		output = new Output();
		textArea = new mbJTextArea(parent);
		try {
			XMLInterpreter inter = new XMLInterpreter(fileName);
			schedulingTree = inter.getScTree();
			treeArea = new ComponentTreeUI(schedulingTree, output, parent);
			setTabs();
		} catch (Exception e) {
			Frame frame = new Frame();
			JOptionPane.showMessageDialog(frame, "Not a valid CARTS XML input");
		}
		editor=parent;

	}

	public mbJTextArea getTextArea() {
		return textArea;
	}

	public ComponentTreeUI getTreeArea() {
		return treeArea;
	}

	public JSplitPane getComponent() {
		return topBottom;
	}

	/**
	 * Builds a Scheduling Tree object for a given XML file. The Tree View is
	 * also reconstructed.
	 * 
	 * @param fileName
	 */
	public void convertToTree(String fileName) {
		if (editor==null)
		{
			System.out.println("ERROR:EDITOR... Component AREA");
			System.exit(1);
		}
		//xm: only interpret tree structure. Parse the xml file when user choose to compute a resource model
		XMLInterpreter inter = new XMLInterpreter(fileName); 
		if(!inter.readFile()){
			UserUtil.showErr(inter.getErrorMsg());
			return;
		}
		schedulingTree = inter.getScTree();

		treeArea = new ComponentTreeUI(schedulingTree, output,editor);
		leftRight.setLeftComponent(treeArea);
		leftRight.setDividerLocation(400);
	}

	/**
	 * Calls the Scheduling Tree object to write its details into the given XML
	 * file
	 * 
	 * @param fileName
	 */
	public void convertToXML(String fileName) {
		treeArea.convertToXML(fileName);
	}
}
