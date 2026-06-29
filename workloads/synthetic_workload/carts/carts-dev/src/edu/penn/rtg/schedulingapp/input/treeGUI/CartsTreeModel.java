package edu.penn.rtg.schedulingapp.input.treeGUI;

import javax.swing.JTree;
import javax.swing.tree.DefaultMutableTreeNode;
import javax.swing.tree.DefaultTreeModel;
import javax.swing.tree.TreePath;

public class CartsTreeModel{
	private DefaultTreeModel treeModel;
	private JTree tree;
	public CartsTreeModel(DefaultTreeModel treeModel, JTree tree) {
		super();
		this.treeModel = treeModel;
		this.tree = tree;
	}
	
	/**
	 * Add child to the currently selected node in JTree.
	 */
	protected void addObject(DefaultMutableTreeNode parent,
			DefaultMutableTreeNode child) {
		treeModel.insertNodeInto(child, parent, parent.getChildCount());
		tree.scrollPathToVisible(new TreePath(child.getPath()));
	}
	/**
	 * Removes the node from JTree
	 * 
	 * @param node
	 */
	protected void removeObject(DefaultMutableTreeNode node) {
		treeModel.removeNodeFromParent(node);
	}


}
