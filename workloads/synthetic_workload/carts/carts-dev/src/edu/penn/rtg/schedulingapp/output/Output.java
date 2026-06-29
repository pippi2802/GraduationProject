package edu.penn.rtg.schedulingapp.output;

import java.awt.BorderLayout;
import java.awt.Dimension;
import java.awt.event.ActionEvent;
import java.awt.event.ActionListener;
import java.awt.event.MouseEvent;
import java.awt.event.MouseListener;

import javax.swing.ImageIcon;
import javax.swing.JButton;
import javax.swing.JFileChooser;
import javax.swing.JLabel;
import javax.swing.JPanel;
import javax.swing.JScrollPane;
import javax.swing.JToolBar;
import javax.swing.JTree;
import javax.swing.tree.DefaultMutableTreeNode;
import javax.swing.tree.DefaultTreeModel;
import javax.swing.tree.TreePath;
import javax.swing.tree.TreeSelectionModel;

import com.jpe.Constants;

import edu.penn.rtg.schedulingapp.SchedulingComponent;
import edu.penn.rtg.schedulingapp.TreeComponent;
import edu.penn.rtg.schedulingapp.input.treeGUI.CartsTableRenderer;

/**
 * Output class renders the output of the analysis on the Scheduling Tree on the
 * UI. It builds a JTree object to display the result as a tree. It also
 * provides option of saving the result as an XML
 */
@SuppressWarnings("serial")
public class Output extends JPanel implements OutputI, ActionListener,
		MouseListener {
	JButton saveButton;
	String algorithm = "";
	JLabel algoLabel;
	TreeComponent rootComponent;

	public Output() {
		super(new BorderLayout(2, 0));
		initialize();
	}

	/**
	 * Sets up the UI on which the output will be rendered
	 */
	protected void initialize() {
		JToolBar toolBar = new JToolBar();
		algoLabel = new JLabel();
		
		saveButton = new JButton(new ImageIcon("images/save16.gif"));
		saveButton.setFont(Constants.SYSTEM_FONT);
		saveButton.setPreferredSize(new Dimension(16, 16));
		saveButton.setBorderPainted(false);
		saveButton.setToolTipText("Save Output as XML");
		saveButton.addActionListener(this);
		saveButton.setBorderPainted(false);
		saveButton.addMouseListener(this);
		saveButton.setEnabled(false);

		toolBar.add(saveButton);
		toolBar.addSeparator(Constants.r);
		toolBar.add(algoLabel);

		add(toolBar, BorderLayout.NORTH);
	}
	@Override
	public void displayEmpty() {
		// TODO Auto-generated method stub
		this.removeAll();

		initialize();
		algoLabel.setText("");
		saveButton.setEnabled(false);
		this.updateUI();
		
	}

	
	/**
	 * Displays the output present in the Scheduling Component as a tree in the
	 * Panel from which this class is extended
	 */
	public void displayOutput(TreeComponent comp, String algo) {
		this.removeAll();

		initialize();
		algorithm = new String(algo);
		algoLabel.setText("Analysis Result with " + algorithm);
		rootComponent = comp;
		CompOutputRenderer compNameNode = new CompOutputRenderer(rootComponent.getCompName());
		DefaultTreeModel treeModel = new DefaultTreeModel(compNameNode);
		JTree tree = new JTree(treeModel);
		tree.setEditable(false);
		tree.getSelectionModel().setSelectionMode(
				TreeSelectionModel.SINGLE_TREE_SELECTION);
		tree.setShowsRootHandles(true);
		tree.setScrollsOnExpand(true);

		displayOutput(treeModel, tree, rootComponent, compNameNode);
		
		//JTreeExpander.expandJTree(tree, -1);//expand all rows and sub-nodes of tree
		
		JScrollPane scrollPane = new JScrollPane(tree);
		add(scrollPane, BorderLayout.CENTER);

		tree.setCellRenderer(new CartsTableRenderer());
		saveButton.setEnabled(true);
		this.updateUI();
	}

	/**
	 * Parses the process models in the components and builds a JTree from its
	 * values
	 * 
	 * @param treeModel
	 * 
	 * @param tree
	 *            Tree on which the output values will be displayed
	 * @param comp
	 *            Scheduling Component whose values need to be displayed
	 * @param compNameNode
	 */
	protected void displayOutput(DefaultTreeModel treeModel, JTree tree,
			TreeComponent comp, DefaultMutableTreeNode compNameNode) {
		String[] multiLinesResource = comp.getResourceModelList().toString()
				.split("\n");
		String[] multiLinesTask = comp.getProcessedTaskList().toString().split(
				"\n");
		//padding the string to a fixed width to avoid displayed test collapsed
		//int strLength = findMaxStringLength(comp);
		int strLength = 60;
		padStrings(multiLinesResource, strLength);
		padStrings(multiLinesTask, strLength);
		
		ResourceModelRenderer resourceNameNode = new ResourceModelRenderer(
				padString("Resource Model", strLength));
		treeModel.insertNodeInto(resourceNameNode, compNameNode, compNameNode
				.getChildCount());
//		treeModel.insertNodeInto(resourceNameNode, compNameNode,0);
//		treeModel.nodeChanged(resourceNameNode);
//		treeModel.nodeChanged(compNameNode);
		tree.scrollPathToVisible(new TreePath(resourceNameNode.getPath()));
		//tree.expandPath(new TreePath(resourceNameNode.getPath()));
		
		for (String model : multiLinesResource) {
			int index = 0;
			ModelRenderer resourceNode = new ModelRenderer(model);
			treeModel.insertNodeInto(resourceNode, resourceNameNode,
					resourceNameNode.getChildCount());
//			treeModel.insertNodeInto(resourceNode, resourceNameNode,index);
//			treeModel.nodeChanged(resourceNode);
//			treeModel.nodeChanged(resourceNameNode);
			tree.scrollPathToVisible(new TreePath(resourceNode.getPath()));
			index++;
			//tree.expandPath(new TreePath(resourceNode.getPath()));
		}

		ProcessedTaskModelRenderer taskNameNode = new ProcessedTaskModelRenderer(
				padString("Processed Task Model ", strLength));
		treeModel.insertNodeInto(taskNameNode, compNameNode, compNameNode
				.getChildCount());
//		treeModel.insertNodeInto(taskNameNode, compNameNode, 1);
		tree.scrollPathToVisible(new TreePath(taskNameNode.getPath()));
		//tree.expandPath(new TreePath(taskNameNode.getPath()));

		for (String model : multiLinesTask) {
			if(model.contains("Period")){
				int index = 0;
				ModelRenderer taskNode = new ModelRenderer(model);
				treeModel.insertNodeInto(taskNode, taskNameNode, taskNameNode
						.getChildCount());
//				treeModel.insertNodeInto(taskNode, taskNameNode, index);
//				treeModel.nodeChanged(taskNode);
//				treeModel.nodeChanged(taskNameNode);
				tree.scrollPathToVisible(new TreePath(taskNode.getPath()));
			//	tree.expandPath(new TreePath(taskNode.getPath()));
				tree.makeVisible(new TreePath(taskNode.getPath()));
				index++;
			}
		}

		for (TreeComponent component : comp.getAllChildren()) {
			CompOutputRenderer subCompNameNode = new CompOutputRenderer(
					padString(component.getCompName(),strLength));
			int index = 2;
			treeModel.insertNodeInto(subCompNameNode, compNameNode,
					compNameNode.getChildCount());
//			treeModel.insertNodeInto(subCompNameNode, compNameNode,index);
//			treeModel.nodeChanged(subCompNameNode);
//			treeModel.nodeChanged(compNameNode);
			tree.scrollPathToVisible(new TreePath(subCompNameNode.getPath()));
		//	tree.expandPath(new TreePath(subCompNameNode.getPath()));
			displayOutput(treeModel, tree, component, subCompNameNode);
		}
	}

	/**
	 * Handles the save option when exercised by the user
	 */
	@Override
	public void actionPerformed(ActionEvent e) {
		if (e.getSource() == saveButton) {
			JFileChooser jfileChooser = new JFileChooser();
			jfileChooser.setAlignmentX(CENTER_ALIGNMENT);
			jfileChooser.setDialogTitle("Save Output As");
			jfileChooser.setApproveButtonText("Save");
			jfileChooser.setFont(Constants.SYSTEM_FONT);

			if (jfileChooser.showOpenDialog(this) == JFileChooser.APPROVE_OPTION) {
				String fileName = jfileChooser.getSelectedFile().getPath();
				XMLOutput.writeOutput(rootComponent, fileName, algorithm);
			}
		}
	}

	@Override
	public void mouseClicked(MouseEvent arg0) {
	}

	@Override
	public void mouseEntered(MouseEvent arg0) {
	}

	@Override
	public void mouseExited(MouseEvent arg0) {
	}

	@Override
	public void mousePressed(MouseEvent arg0) {
	}

	@Override
	public void mouseReleased(MouseEvent arg0) {
	}
	
	public int findMaxStringLength(String[] strs){
		int length_max = 1;
		for(int i=0; i<strs.length; i++){
			if(length_max < strs[i].length()){
				length_max = strs[i].length();
			}
		}
		return length_max;
	}
	
	public int findMaxStringLength(TreeComponent comp){
		int strLengthMaxWholeTree = 0;
		String[] multiLinesResource = comp.getResourceModelList().toString()
				.split("\n");
		String[] multiLinesTask = comp.getProcessedTaskList().toString().split(
				"\n");
		//padding the string to a fixed width to avoid displayed test collapsed
		int strLength1 = findMaxStringLength(multiLinesResource);
		int strlength2 = findMaxStringLength(multiLinesTask);
		strLengthMaxWholeTree = Math.max(strLength1, strlength2);
		for(TreeComponent childComp: comp.getAllChildren()){
			int strLengthMaxChild = findMaxStringLength(childComp);
			if(strLengthMaxWholeTree < strLengthMaxChild){
				strLengthMaxWholeTree = strLengthMaxChild;
			}
		}
		return strLengthMaxWholeTree;
	}
	
	public void padStrings(String[] strs, int strLength){
		for(int i=0; i<strs.length; i++){
			strs[i] = String.format("%-" + strLength + "s", strs[i]);
			System.out.println("padded string: "+strs[i] + ".");
		}
	}
	
	public String padString(String str, int strLength){
		str = String.format("%-" + strLength + "s", str);
		System.out.println("padded string: "+ str + ".");
		return str;
	}

}
