package edu.penn.rtg.schedulingapp.output;

/**
 * Expand a JTree recursively for a specific depth 
 * Code is from  website http://www.jguru.com/faq/view.jsp?EID=513951
 *
 */
public class JTreeExpander {
	/**
	 * Expands all nodes in a JTree.
	 *
	 * @param tree      The JTree to expand.
	 * @param depth     The depth to which the tree should be expanded.  Zero
	 *                  will just expand the root node, a negative value will
	 *                  fully expand the tree, and a positive value will
	 *                  recursively expand the tree to that depth.
	 */
	public static void expandJTree (javax.swing.JTree tree, int depth)
	{
	    javax.swing.tree.TreeModel model = tree.getModel();
	    expandJTreeNode(tree, model, model.getRoot(), 0, depth);
	} // expandJTree()


	/**
	 * Expands a given node in a JTree.
	 *
	 * @param tree      The JTree to expand.
	 * @param model     The TreeModel for tree.     
	 * @param node      The node within tree to expand.     
	 * @param row       The displayed row in tree that represents
	 *                  node.     
	 * @param depth     The depth to which the tree should be expanded. 
	 *                  Zero will just expand node, a negative
	 *                  value will fully expand the tree, and a positive
	 *                  value will recursively expand the tree to that
	 *                  depth relative to node.
	 */
	public static int expandJTreeNode (javax.swing.JTree tree,
	                                   javax.swing.tree.TreeModel model,
	                                   Object node, int row, int depth)
	{
	    if (node != null  &&  !model.isLeaf(node)) {
	        tree.expandRow(row);
	        if (depth != 0)
	        {
	            for (int index = 0;
	                 row + 1 < tree.getRowCount()  &&  
	                            index < model.getChildCount(node);
	                 index++)
	            {
	                row++;
	                Object child = model.getChild(node, index);
	                if (child == null)
	                    break;
	                javax.swing.tree.TreePath path;
	                while ((path = tree.getPathForRow(row)) != null  &&
	                        path.getLastPathComponent() != child)
	                    row++;
	                if (path == null)
	                    break;
	                row = expandJTreeNode(tree, model, child, row, depth - 1);
	            }
	        }
	    }
	    return row;
	} // expandJTreeNode()
}
