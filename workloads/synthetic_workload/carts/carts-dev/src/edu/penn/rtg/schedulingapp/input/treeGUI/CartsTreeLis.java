package edu.penn.rtg.schedulingapp.input.treeGUI;


import javax.swing.event.TreeModelEvent;
import javax.swing.event.TreeModelListener;
import edu.penn.rtg.schedulingapp.TreeComponent;

public class CartsTreeLis implements TreeModelListener {
	public void treeNodesChanged(TreeModelEvent e) {
		TreeComponent node;
		node = (TreeComponent) (e.getTreePath()
				.getLastPathComponent());

		int index = e.getChildIndices()[0];
		node = (TreeComponent) (node.getChildAt(index));
	}

	public void treeNodesInserted(TreeModelEvent e) {
	}

	public void treeNodesRemoved(TreeModelEvent e) {
	}

	public void treeStructureChanged(TreeModelEvent e) {
	}
}
